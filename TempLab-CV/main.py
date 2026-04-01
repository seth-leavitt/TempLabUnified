import os
import time
import numpy as np

from src.laserDetector import LaserDetector
import cv2

def combined_image(images, row_size = 2):
    # Concatenate images to form a grid
    image_array = [[]]
    for image in images:
        row = image_array[-1]
        if len(row) < row_size:
            row.append(image)
        else:
            image_array.append([image])
    while len(image_array[-1]) < row_size:
        image_array[-1].append(np.zeros_like(image_array[-1][0]))
    rows = []
    for row in image_array:
        row = np.hstack(row)
        rows.append(row)
    final_image = np.vstack(rows)
    cv2.imshow("steps", final_image)
    cv2.waitKey(0)
    return final_image


def test_laser_detector():
    start = time.perf_counter()
    test_image = cv2.imread("test_images/img.png")
    cv2.imshow("test_image", test_image)
    images = [test_image]
    color = np.array([[[0, 0, 255]]], dtype=np.uint8)
    laserDetector = LaserDetector(color, image=test_image.copy())
    hsv, masked = laserDetector.mask(color, return_images=True)
    images.append(hsv)
    images.append(masked)
    contours = laserDetector.find_contours().copy()
    images.append(contours)
    ellipse_image, position, axis, angle = laserDetector.fit_ellipse()
    ellipse_image = ellipse_image.copy()
    images.append(ellipse_image)
    end = time.perf_counter()

    print(f"Time taken: {end - start} seconds")
    # Resize images to a common height
    max_height = max(img.shape[0] for img in images)
    resized_images = [cv2.resize(img, (int(img.shape[1] * max_height / img.shape[0]), max_height)) for img in images]
    image_grid = combined_image(resized_images)
    cv2.imshow("steps", image_grid)
    cv2.imwrite("test_images/steps.png", image_grid)