from typing import Any, Optional

import cv2
import numpy as np

from .detector import LaserDetector

try:
    import gxipy
except Exception:
    gxipy = None


class CVManager:
    """Camera and laser-detection manager shared by the GUI camera tab.

    This class keeps camera stream lifecycle, frame acquisition, and laser
    distance estimation in one place so the UI layer stays lightweight.
    """

    def __init__(self):
        # Color references used by the laser detector instances.
        self.green = np.array([[[0, 255, 0]]], dtype=np.uint8)
        self.red = np.array([[[0, 0, 255]]], dtype=np.uint8)
        self.green_laser = LaserDetector(self.green)
        self.red_laser = LaserDetector(self.red)

        # Camera SDK objects are populated lazily when connection starts.
        self.device_manager: Optional[Any] = None
        self.camera_stream: Optional[Any] = None
        self.exposure_us = 100000

    def initialize_camera_stream(self):
        """Open the first available camera and enable continuous acquisition."""
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
        camera.ExposureTime.set(self.exposure_us)
        camera.stream_on()
        self.camera_stream = camera

    def set_exposure(self, exposure_us):
        """Set camera exposure in microseconds and apply immediately if connected."""
        exposure = int(float(exposure_us))
        if exposure <= 0:
            raise ValueError("Exposure must be a positive number of microseconds")

        self.exposure_us = exposure
        if self.camera_stream is not None:
            self.camera_stream.ExposureTime.set(self.exposure_us)

    def close_camera_stream(self):
        """Stop and close the active camera stream safely."""
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
        """Convert gxipy frame objects into OpenCV-friendly numpy arrays."""
        if raw_img is None:
            return None

        if hasattr(raw_img, "get_numpy_array"):
            arr = raw_img.get_numpy_array()
            if isinstance(arr, np.ndarray) and arr.ndim == 3 and arr.shape[2] == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return arr

        raise TypeError(
            "Unsupported gxipy image object; expected get_numpy_array() support "
            f"but got {type(raw_img)}"
        )

    def capture_image(self):
        """Capture one frame and update detector input images.

        The SDK can provide either Bayer mono frames or 3-channel frames,
        so conversion is conditional to avoid unnecessary work.
        """
        if self.camera_stream is None:
            self.initialize_camera_stream()
        if self.camera_stream is None:
            raise RuntimeError("Camera stream is not initialized")

        image = self.camera_stream.data_stream[0].get_image()
        image = self.rawimage_to_cv2(image)
        if image is None:
            raise RuntimeError("Failed to read camera frame")
        if len(image.shape) == 2:
            frame_bgr = cv2.cvtColor(image, cv2.COLOR_BAYER_RG2BGR)
        elif len(image.shape) == 3 and image.shape[2] == 3:
            frame_bgr = image
        else:
            raise RuntimeError(f"Unsupported frame shape from camera: {image.shape}")

        self.green_laser.image = frame_bgr
        self.red_laser.image = frame_bgr
        return frame_bgr

    def find_distance(self):
        """Detect red/green laser spots and return pixel-space distance."""
        image = self.capture_image()
        return self.find_distance_from_frame(image)

    def find_distance_from_frame(self, image):
        """Detect red/green laser spots from a provided BGR frame."""
        if image is None:
            return 0
        self.green_laser.image = image
        self.red_laser.image = image

        green = self.green_laser.detect(0)
        red = self.red_laser.detect(0)
        if green is None or red is None:
            return 0

        green_pos = np.array(green[0])
        red_pos = np.array(red[0])
        return float(np.linalg.norm(green_pos - red_pos))
