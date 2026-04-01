from typing import Any, Optional

import cv2
import numpy as np

from .detector import LaserDetector

try:
    import gxipy
except Exception:
    gxipy = None


class CVManager:
    def __init__(self):
        self.green = np.array([[[0, 255, 0]]], dtype=np.uint8)
        self.red = np.array([[[0, 0, 255]]], dtype=np.uint8)
        self.green_laser = LaserDetector(self.green)
        self.red_laser = LaserDetector(self.red)
        self.device_manager: Optional[Any] = None
        self.camera_stream: Optional[Any] = None

    def initialize_camera_stream(self):
        if self.camera_stream is not None:
            return
        if gxipy is None:
            raise RuntimeError("gxipy is not installed; camera stream is unavailable")

        self.device_manager = gxipy.DeviceManager()
        device_num, _ = self.device_manager.update_device_list()
        if device_num == 0:
            raise RuntimeError("No camera device found")

        camera = self.device_manager.open_device_by_index(1)
        if camera is None:
            raise RuntimeError("Unable to open camera device")

        camera.TriggerMode.set(False)
        camera.ExposureTime.set(100000)
        camera.stream_on()
        self.camera_stream = camera

    def close_camera_stream(self):
        cam = self.camera_stream
        self.camera_stream = None
        if cam is None:
            return
        try:
            cam.stream_off()
        except Exception:
            pass
        try:
            cam.close_device()
        except Exception:
            pass

    def rawimage_to_cv2(self, raw_img):
        if raw_img is None:
            return None

        if hasattr(raw_img, "get_numpy_array"):
            arr = raw_img.get_numpy_array()
            if isinstance(arr, np.ndarray) and arr.ndim == 3 and arr.shape[2] == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return arr

        if gxipy is None:
            raise RuntimeError("gxipy is not installed; camera stream is unavailable")

        converter = gxipy.ImageFormatConvert()
        try:
            converter.output_pixel_format = gxipy.GxPixelFormatEntry.RGB8
        except Exception:
            pass

        rgb_img = converter.convert(raw_img)
        if hasattr(rgb_img, "get_numpy_array"):
            arr = rgb_img.get_numpy_array()
            if isinstance(arr, np.ndarray) and arr.ndim == 3 and arr.shape[2] == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return arr
        raise TypeError(f"Unsupported gxipy image type: {type(raw_img)}")

    def capture_image(self):
        if self.camera_stream is None:
            self.initialize_camera_stream()
        if self.camera_stream is None:
            raise RuntimeError("Camera stream is not initialized")

        image = self.camera_stream.data_stream[0].get_image()
        image = self.rawimage_to_cv2(image)
        if image is None:
            raise RuntimeError("Failed to read camera frame")
        rgb = cv2.cvtColor(image, cv2.COLOR_BAYER_RG2RGB)
        self.green_laser.image = rgb.copy()
        self.red_laser.image = rgb.copy()
        return rgb

    def find_distance(self):
        image = self.capture_image()
        self.green_laser.image = image.copy()
        self.red_laser.image = image.copy()

        green = self.green_laser.detect(0)
        red = self.red_laser.detect(0)
        if green is None or red is None:
            return 0

        green_pos = np.array(green[0])
        red_pos = np.array(red[0])
        return float(np.linalg.norm(green_pos - red_pos))
