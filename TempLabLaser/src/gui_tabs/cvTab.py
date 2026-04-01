import tkinter as tk
from PIL import Image, ImageTk
import cv2

from src.cv import CVManager


class CVTab:
    def __init__(self, parent):
        self.parent = parent
        self.cv_manager = CVManager()
        self.viewport_running = False
        self.viewport_job = None
        self.current_image = None
        self.setup_ui()

    def setup_ui(self):
        controls = tk.Frame(self.parent)
        controls.pack(fill="x", padx=10, pady=10)

        self.connect_btn = tk.Button(controls, text="Connect Camera", command=self.connect_camera)
        self.connect_btn.pack(padx=10, pady=10)

        self.capture_btn = tk.Button(controls, text="Capture Frame", command=self.capture_frame)
        self.capture_btn.pack(padx=10, pady=10)

        self.start_viewport_btn = tk.Button(controls, text="Start Viewport", command=self.start_viewport)
        self.start_viewport_btn.pack(padx=10, pady=10)

        self.stop_viewport_btn = tk.Button(controls, text="Stop Viewport", command=self.stop_viewport, state=tk.DISABLED)
        self.stop_viewport_btn.pack(padx=10, pady=10)

        self.distance_btn = tk.Button(controls, text="Find Laser Distance", command=self.find_distance)
        self.distance_btn.pack(padx=10, pady=10)

        self.viewport_label = tk.Label(self.parent, text="Camera viewport not started", width=90, height=30)
        self.viewport_label.pack(fill="both", expand=True, padx=10, pady=10)

        self.output = tk.Text(self.parent, height=10, font=("Arial", 14))
        self.output.pack(fill="both", expand=True, padx=10, pady=10)

    def _write(self, message):
        self.output.insert(tk.END, f"{message}\n")
        self.output.see(tk.END)

    def connect_camera(self):
        try:
            self.cv_manager.initialize_camera_stream()
            self._write("Camera stream initialized")
        except Exception as exc:
            self._write(f"Camera init failed: {exc}")

    def capture_frame(self):
        try:
            image = self.cv_manager.capture_image()
            self._update_viewport(image)
            shape = getattr(image, "shape", None)
            self._write(f"Captured image: shape={shape}")
        except Exception as exc:
            self._write(f"Capture failed: {exc}")

    def _update_viewport(self, frame):
        if frame is None:
            return
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        else:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        image = Image.fromarray(frame)
        image.thumbnail((900, 600))
        self.current_image = ImageTk.PhotoImage(image=image)
        self.viewport_label.config(image=self.current_image, text="")

    def _viewport_tick(self):
        if not self.viewport_running:
            return
        try:
            frame = self.cv_manager.capture_image()
            self._update_viewport(frame)
        except Exception as exc:
            self._write(f"Viewport update failed: {exc}")
            self.stop_viewport()
            return
        self.viewport_job = self.parent.after(33, self._viewport_tick)

    def start_viewport(self):
        if self.viewport_running:
            return
        try:
            self.cv_manager.initialize_camera_stream()
            self.viewport_running = True
            self.start_viewport_btn.config(state=tk.DISABLED)
            self.stop_viewport_btn.config(state=tk.NORMAL)
            self._write("Viewport started")
            self._viewport_tick()
        except Exception as exc:
            self._write(f"Viewport start failed: {exc}")

    def stop_viewport(self):
        self.viewport_running = False
        if self.viewport_job is not None:
            self.parent.after_cancel(self.viewport_job)
            self.viewport_job = None
        self.start_viewport_btn.config(state=tk.NORMAL)
        self.stop_viewport_btn.config(state=tk.DISABLED)
        self.cv_manager.close_camera_stream()
        self._write("Viewport stopped")

    def find_distance(self):
        try:
            distance = self.cv_manager.find_distance()
            self._write(f"Detected laser distance: {distance}")
        except Exception as exc:
            self._write(f"Distance calc failed: {exc}")
