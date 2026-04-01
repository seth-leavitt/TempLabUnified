import cv2
import numpy as np
import laserDetector as ld
import traceback

try:
    import gxipy
except:
    traceback.print_exc()
    print("Daheng GalaxyView SDK not installed. \nEither install it or check the file path in python API")

device_manager = gxipy.DeviceManager()
if device_manager is None:
    raise RuntimeError("DeviceManager() returned None (likely SDK/native library issue).")

class CV_Manager:
    def __init__(self):
        # Initialize data objects
        self.green = np.array([[[0, 255, 0]]], dtype=np.uint8)
        self.red = np.array([[[0, 0, 255]]], dtype=np.uint8)
        self.green_laser = ld.LaserDetector(self.green)
        self.red_laser = ld.LaserDetector(self.red)

        # Declare device interfaces
        self.device_manager = device_manager
        self.camera_stream = None
        self.initialize_camera_stream()
        self.image = self.capture_image()
        print(f"image type: {type(self.image)}")

    def set_camera_mode(self, exposure = 100000):
        if self.camera_stream is None:
            self.initialize_camera_stream()
        self.camera_stream.TriggerMode.set(False)
        self.camera_stream.ExposureTime.set(exposure)

    def initialize_camera_stream(self):
        if self.camera_stream is not None:
            return
        self.device_manager = gxipy.DeviceManager()
        # The implementation here is slightly different from the C version of the API
        device_num, device_info = self.device_manager.update_device_list()

        print(f"Number of cameras found: {device_num} \nCamera info: {device_info}")
        if device_num == 0:
            raise RuntimeError("No camera device found!")
        try:
            self.camera_stream = self.device_manager.open_device_by_index(1)
            self.set_camera_mode()
        except Exception as e:
            raise RuntimeError(
                "Camera is already in use (likely the vendor app). Close it and retry."
            ) from e

        self.camera_stream.stream_on()

    def close_camera_stream(self):
        cam = self.camera_stream
        self.camera_stream = None

        if cam is None:
            return

        # Be defensive: gxipy may raise if already stopped/closed
        try:
            cam.stream_off()
        except Exception:
            pass

        try:
            cam.close_device()
        except Exception:
            pass

    def rawimage_to_cv2(self, raw_img):
        """
        Convert gxipy.ImageProc.RawImage -> OpenCV image (numpy.ndarray).
        Returns either:
          - HxW (mono)
          - HxWx3 (BGR)
        """
        if raw_img is None:
            return None

            # Fast-path: some gxipy versions expose direct numpy conversion
        if hasattr(raw_img, "get_numpy_array"):
            arr = raw_img.get_numpy_array()
            # If it's RGB, convert to BGR for OpenCV display consistency
            if isinstance(arr, np.ndarray) and arr.ndim == 3 and arr.shape[2] == 3:
                # Many SDKs deliver RGB; if your colors look swapped, keep this conversion.
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return arr

            # Generic path: use gxipy converter (works for Bayer/Mono/packed formats in many cases)
        converter = gxipy.ImageFormatConvert()
        # Try to ask for an 8-bit RGB output if supported by your camera/SDK
        # (If your gxipy build uses different enums, adjust these constants accordingly.)
        try:
            converter.output_pixel_format = gxipy.GxPixelFormatEntry.RGB8
        except Exception:
            # Fallback: leave default if enum name differs in this gxipy version
            pass

        rgb_img = converter.convert(raw_img)
        if rgb_img is None:
            raise RuntimeError("gxipy conversion returned None")

        # Many gxipy converted image objects provide get_numpy_array() even if RawImage doesn't
        if hasattr(rgb_img, "get_numpy_array"):
            arr = rgb_img.get_numpy_array()
            if isinstance(arr, np.ndarray) and arr.ndim == 3 and arr.shape[2] == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return arr

        raise TypeError(f"Don't know how to convert gxipy image type: {type(raw_img)}")

    def capture_image(self):
        if self.camera_stream is None:
            self.initialize_camera_stream()
        if self.camera_stream is None:
            print("Camera stream not initialized!")
            return None
        image = self.camera_stream.data_stream[0].get_image()
        # print(f"raw image type: {type(image)}") #DEBUGGING CODE
        image = self.rawimage_to_cv2(image)

        rgb = cv2.cvtColor(image, cv2.COLOR_BAYER_RG2RGB)  # adjust RG/BG/GR/GB to match your sensor

        self.green_laser.image = rgb.copy()
        self.red_laser.image = rgb.copy()

        return rgb

    def find_distance(self):
        # Here we collect the image from the buffer
        image = self.capture_image()
        self.green_laser.image = image.copy()
        self.red_laser.image = image.copy()

        distance = 0
        self.green_laser.detect_laser(window_name = "Green Laser")
        self.red_laser.detect_laser(window_name = "Red Laser")

        green_pos = None
        red_pos = None

        try:
            green_pos, green_axis, green_angle = self.green_laser.ellipse
            green_pos = np.array(green_pos)
            print(green_pos, green_axis, green_angle)
        except TypeError:
            print("No green laser detected")
        try:
            red_pos, red_axis, red_angle = self.red_laser.ellipse
            red_pos = np.array(red_pos)
            print(red_pos, red_axis, red_angle)
        except TypeError:
            print("No red laser detected")

        if green_pos is not None and red_pos is not None:
            distance = np.linalg.norm(green_pos - red_pos)
            print(f"Distance calculated: {distance * 0.24 / 5} mm (Check the Conversion Ratio)")
            return distance
        else:
            print("Error in distance calculation")
            return 0

    def characterize_lasers(self):
        def gradient_along_axis(ellipse, color, minor_axis):
            THRESHOLD = .7
            pixels_of_interest = []
            pos, axis, angle = ellipse
            if minor_axis is True:
                angle += 90
            print(f"Angle of {'minor axis' if minor_axis else 'major axis'} gradient: {angle} Degrees")
            color = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)
            image = cv2.cvtColor(self.image.copy(), cv2.COLOR_BGR2HSV)
            y, x = int(round(pos[1])), int(round(pos[0]))
            pixel = image[y, x]
            gradient_list = []
            gradient_list.append(((y, x), pixel))
            i = 0
            while (1 - THRESHOLD) * 255 <= pixel[2] <= 255 and THRESHOLD * color[0][0][0] <= pixel[0] <= (
                    2 - THRESHOLD) * \
                    color[0][0][0]:  # this will check the saturation and value
                # walk in the positive direction and collect data
                x_change = np.cos(angle) * i
                y_change = np.sin(angle) * i  # we need to round because cos and sin are floats and we need pixel values
                new_x = x + x_change
                new_y = y + y_change
                i += 1
                if (new_y, new_x) == (y, x):
                    # if it rounded to the same position, we need to do it again
                    continue
                else:
                    print(f"iterations required: {i}")
                    i = 0
                    y, x = new_y, new_x
                    pixel_y, pixel_x = int(round(y)), int(round(x))
                    pixel = image[pixel_y, pixel_x]
                    gradient_list.append(((pixel_y, pixel_x), pixel))
            # now we need to walk in the negative direction doing the exact same thing
            i = 0
            y, x = int(round(pos[1])), int(round(pos[0]))  # reset the position to the starting point
            pixel = image[y, x]
            print("Now going backwards...")
            while (1 - THRESHOLD) * 255 <= pixel[2] <= 255 and THRESHOLD * color[0][0][0] <= pixel[0] <= (
                    2 - THRESHOLD) * \
                    color[0][0][0]:  # this will check the saturation and value
                # walk in the negative direction and collect data
                x_change = np.cos(angle) * -i
                y_change = np.sin(
                    angle) * -i  # we need to round because cos and sin are floats and we need pixel values
                new_x = x + x_change
                new_y = y + y_change
                i += 1
                if (new_y, new_x) == (y, x):
                    # if it rounded to the same position, we need to do it again
                    continue
                else:
                    print(f"iterations required: {i}")
                    i = 0
                    y, x = new_y, new_x
                    pixel_y, pixel_x = int(round(y)), int(round(x))
                    pixel = image[pixel_y, pixel_x]
                    gradient_list.append(((pixel_y, pixel_x), pixel))

            return gradient_list

        green_pos, green_axis, green_angle = self.green_laser.ellipse
        red_pos, red_axis, red_angle = self.red_laser.ellipse
        green_pos = np.array(green_pos)
        red_pos = np.array(red_pos)

        green_along_major = gradient_along_axis(self.green_laser.ellipse, self.green, False)
        green_along_minor = gradient_along_axis(self.green_laser.ellipse, self.green, True)
        print(green_along_major)
        print(green_along_minor)

        print(f"Number of pixels along major axis: {len(green_along_major)}")
        print(f"Number of pixels along minor axis: {len(green_along_minor)}")

    def __del__(self):
        print("Garbage collector: CV_Manager destroyed")
        if self.camera_stream is not None:
            self.camera_stream.stream_off()
            self.camera_stream.close_device()
        else:
            print("No Camera Stream was active at time of garbage collection")



if __name__ == "__main__":
    cv_manager = CV_Manager()
    # print(f"distance calculated: {cv_manager.find_distance() * 0.24 / 5}")
    # cv_manager.characterize_lasers()
