import cv2
import numpy as np


class LaserDetector:
    def __init__(self, color, image=None):
        self.CUTOFF_LENGTH = 10
        self.color = color
        self.contours = None
        self.ellipse = None
        self.image = image

    def mask(self, color=None, s_min=20, v_min=80):
        if color is None:
            color = self.color
        if self.image is None:
            return None

        if isinstance(color, (tuple, list)):
            color = np.array([[color]], dtype=np.uint8)
        else:
            color = np.asarray(color, dtype=np.uint8)
            if color.shape == (3,):
                color = color.reshape((1, 1, 3))

        img = self.image
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        hsv_color = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)
        h = int(hsv_color[0, 0, 0])
        hsv_image = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        low_h = (h - self.CUTOFF_LENGTH) % 180
        high_h = (h + self.CUTOFF_LENGTH) % 180

        if low_h <= high_h:
            lower = np.array([low_h, s_min, v_min], dtype=np.uint8)
            upper = np.array([high_h, 255, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv_image, lower, upper)
        else:
            lower1 = np.array([0, s_min, v_min], dtype=np.uint8)
            upper1 = np.array([high_h, 255, 255], dtype=np.uint8)
            lower2 = np.array([low_h, s_min, v_min], dtype=np.uint8)
            upper2 = np.array([179, 255, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv_image, lower1, upper1) | cv2.inRange(hsv_image, lower2, upper2)

        return mask

    def find_contours(self):
        masked = self.mask()
        self.contours, _ = cv2.findContours(masked, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    def fit_ellipse(self, contour_selection=0):
        if not self.contours:
            return None
        largest_contours = sorted(self.contours, key=cv2.contourArea, reverse=True)
        if contour_selection >= len(largest_contours):
            return None
        contour = largest_contours[contour_selection]
        self.ellipse = cv2.fitEllipse(contour)
        return self.ellipse

    def detect(self, contour_selection=0):
        self.find_contours()
        return self.fit_ellipse(contour_selection=contour_selection)
