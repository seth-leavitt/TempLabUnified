import numpy as np
import cv2

class LaserDetector:
    def __init__(self, color, image=None):
        self.CUTOFF_LENGTH = 10
        self.color = color
        self.contours = None
        self.ellipse = None
        self.image = image

    def mask(self, color=None, s_min=20, v_min=80, return_images=False):
        if color is None:
            color = self.color
        if self.image is None:
            return None

        # Normalize color to 1x1x3 uint8 BGR for cvtColor
        if isinstance(color, tuple) or isinstance(color, list):
            color = np.array([[color]], dtype=np.uint8)
        else:
            color = np.asarray(color, dtype=np.uint8)
            if color.shape == (3,):
                color = color.reshape((1, 1, 3))
            elif color.shape != (1, 1, 3):
                raise ValueError(f"color must be BGR tuple/list or shape (1,1,3); got {color.shape}")

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

        masked = cv2.bitwise_and(img, img, mask=mask)
        if return_images:
            return hsv_image, masked
        return mask


    def find_contours(self):
        masked = self.mask()
        self.contours, hierarchy = cv2.findContours(masked, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        drawn = cv2.drawContours(self.image, self.contours, -1, (255, 0, 0), 1)
        # cv2.imshow("drawn", drawn)
        # cv2.waitKey(0)
        return drawn

    def fit_ellipse(self, contour_selection=1):
        if not self.contours:
            print("No contours found!")
            return None
        largest_contours = sorted(self.contours, key=cv2.contourArea, reverse=True)
        contour = largest_contours[contour_selection]
        ellipse = cv2.fitEllipse(contour)
        print(ellipse)
        self.ellipse = ellipse
        drawn = cv2.ellipse(self.image, ellipse, (0, 255, 0), 2)
        return drawn, *self.ellipse

    def detect_laser(self, contour_selection=0, window_name="laser"):
        import time
        start = time.perf_counter()
        self.mask(self.color)
        self.find_contours()
        self.fit_ellipse(contour_selection=contour_selection)
        end = time.perf_counter()
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.imshow(window_name, self.image)
        cv2.waitKey(0)
        print(f"Time taken: {end - start} seconds")
