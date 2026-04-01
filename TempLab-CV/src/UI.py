from __future__ import annotations

import sys
import cv2
import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget, QLineEdit,
)


def np_bgr_to_qpixmap(frame_bgr: np.ndarray) -> QPixmap:
    """
    Convert an OpenCV BGR uint8 image into a QPixmap for display.
    """
    if frame_bgr is None:
        return QPixmap()

    if frame_bgr.ndim == 2:
        # Mono -> RGB for consistent display
        frame_bgr = cv2.cvtColor(frame_bgr, cv2.COLOR_GRAY2BGR)

    if frame_bgr.dtype != np.uint8:
        # If you have 10/12-bit frames, normalize to 8-bit here as needed.
        frame_bgr = np.clip(frame_bgr, 0, 255).astype(np.uint8)

    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = frame_rgb.shape
    bytes_per_line = ch * w

    qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    # Important: copy() to detach from NumPy memory that will be reused next frame.
    return QPixmap.fromImage(qimg.copy())


class MainWindow(QMainWindow):
    def __init__(self, cv_manager, fps: int = 30):
        super().__init__()
        self.cv_manager = cv_manager

        self.setWindowTitle("Camera Viewer (Qt)")
        self.image_label = QLabel("No frame yet")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 480)

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        self.distance_button = QPushButton("Calculate Distance")
        self.characterize_button = QPushButton("Characterize Lasers")

        self.exposure_label = QLabel("Exposure Time (us):")
        self.exposure_input = QLineEdit("100000")

        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)

        self.distance_button.clicked.connect(self.cv_manager.find_distance)
        self.characterize_button.clicked.connect(self.cv_manager.characterize_lasers)

        self.exposure_input.returnPressed.connect(lambda: self.cv_manager.set_camera_mode(exposure = int(self.exposure_input.text())))

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.start_button)
        btn_row.addWidget(self.stop_button)
        btn_row.addWidget(self.distance_button)
        btn_row.addWidget(self.characterize_button)

        other_row = QHBoxLayout()
        other_row.addWidget(self.exposure_label, stretch=0)
        other_row.addWidget(self.exposure_input, stretch=1)

        root = QVBoxLayout()
        root.addWidget(self.image_label, stretch=1)
        root.addLayout(btn_row)
        root.addLayout(other_row)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

        self.timer = QTimer(self)
        self.timer.setInterval(max(1, int(1000 / fps)))
        self.timer.timeout.connect(self.update_frame)

    def start(self):
        self.timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop(self):
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def update_frame(self):
        # You implement capture_frame() on your manager to return a NumPy image.
        frame = self.cv_manager.capture_image()
        pix = np_bgr_to_qpixmap(frame)
        if not pix.isNull():
            self.image_label.setPixmap(pix.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))

    def closeEvent(self, event):
        # Clean shutdown hook
        try:
            self.stop()
            if hasattr(self.cv_manager, "close"):
                self.cv_manager.close()
        finally:
            super().closeEvent(event)


def run_qt_app(cv_manager):
    app = QApplication(sys.argv)
    win = MainWindow(cv_manager=cv_manager, fps=30)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    import CV_Manager
    cv_manager = CV_Manager.CV_Manager()
    run_qt_app(cv_manager = cv_manager)
