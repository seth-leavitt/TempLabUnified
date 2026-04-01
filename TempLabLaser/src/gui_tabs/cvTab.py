import tkinter as tk
from datetime import datetime
import os

import cv2
from PIL import Image, ImageTk

from src.cv import CVManager


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SHARED_CAPTURE_DIR = os.path.join(PROJECT_ROOT, "shared", "camera_captures")


class CVTab:
    def __init__(self, parent):
        self.parent = parent
        self.cv_manager = CVManager()
        self.viewport_running = False
        self.viewport_job = None
        self.current_image = None
        self.last_frame = None
        self.camera_window = None
        self.viewport_label = None
        self.start_viewport_btn = None
        self.stop_viewport_btn = None
        self.capture_btn = None
        self.distance_btn = None
        self.save_btn = None
        self.setup_ui()

    def setup_ui(self):
        controls = tk.Frame(self.parent)
        controls.pack(fill="x", padx=10, pady=10)

        self.connect_btn = tk.Button(controls, text="Connect Camera", command=self.connect_camera)
        self.connect_btn.pack(padx=10, pady=10)

        self.output = tk.Text(self.parent, height=10, font=("Arial", 14))
        self.output.pack(fill="both", expand=True, padx=10, pady=10)

    def _write(self, message):
        self.output.insert(tk.END, f"{message}\n")
        self.output.see(tk.END)

    def connect_camera(self):
        try:
            self.cv_manager.initialize_camera_stream()
            self._open_camera_window()
            self.start_viewport()
            self._write("Camera stream initialized")
        except Exception as exc:
            self._write(f"Camera init failed: {exc}")

    def _open_camera_window(self):
        if self.camera_window is not None and self.camera_window.winfo_exists():
            self.camera_window.lift()
            return

        self.camera_window = tk.Toplevel(self.parent)
        self.camera_window.title("TempLab Camera Viewport")
        self.camera_window.geometry("1100x820")

        self.viewport_label = tk.Label(self.camera_window, text="Starting camera viewport...")
        self.viewport_label.pack(fill="both", expand=True, padx=10, pady=10)

        command_row = tk.Frame(self.camera_window)
        command_row.pack(fill="x", padx=10, pady=10)

        self.capture_btn = tk.Button(command_row, text="Capture Frame", command=self.capture_frame)
        self.capture_btn.pack(side=tk.LEFT, padx=6, pady=6)

        self.start_viewport_btn = tk.Button(command_row, text="Start Viewport", command=self.start_viewport)
        self.start_viewport_btn.pack(side=tk.LEFT, padx=6, pady=6)

        self.stop_viewport_btn = tk.Button(command_row, text="Stop Viewport", command=self.stop_viewport, state=tk.DISABLED)
        self.stop_viewport_btn.pack(side=tk.LEFT, padx=6, pady=6)

        self.distance_btn = tk.Button(command_row, text="Find Laser Distance", command=self.find_distance)
        self.distance_btn.pack(side=tk.LEFT, padx=6, pady=6)

        self.save_btn = tk.Button(command_row, text="Save Image", command=self.save_image)
        self.save_btn.pack(side=tk.LEFT, padx=6, pady=6)

        self.camera_window.protocol("WM_DELETE_WINDOW", self._on_camera_window_close)

    def _on_camera_window_close(self):
        self.stop_viewport(close_stream=True)
        if self.camera_window is not None:
            self.camera_window.destroy()
        self.camera_window = None
        self.viewport_label = None

    def capture_frame(self):
        try:
            image = self.cv_manager.capture_image()
            self.last_frame = image.copy()
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
        if self.viewport_label is not None:
            self.viewport_label.config(image=self.current_image, text="")

    def _viewport_tick(self):
        if not self.viewport_running:
            return
        try:
            frame = self.cv_manager.capture_image()
            self.last_frame = frame.copy()
            self._update_viewport(frame)
        except Exception as exc:
            self._write(f"Viewport update failed: {exc}")
            self.stop_viewport()
            return
        self.viewport_job = self.parent.after(33, self._viewport_tick)

    def start_viewport(self):
        if self.viewport_running:
            return
        if self.camera_window is None or not self.camera_window.winfo_exists():
            self._open_camera_window()
        try:
            self.cv_manager.initialize_camera_stream()
            self.viewport_running = True
            self.start_viewport_btn.config(state=tk.DISABLED)
            self.stop_viewport_btn.config(state=tk.NORMAL)
            self._write("Viewport started")
            self._viewport_tick()
        except Exception as exc:
            self._write(f"Viewport start failed: {exc}")

    def stop_viewport(self, close_stream=True):
        self.viewport_running = False
        if self.viewport_job is not None:
            self.parent.after_cancel(self.viewport_job)
            self.viewport_job = None
        if self.start_viewport_btn is not None:
            self.start_viewport_btn.config(state=tk.NORMAL)
        if self.stop_viewport_btn is not None:
            self.stop_viewport_btn.config(state=tk.DISABLED)
        if close_stream:
            self.cv_manager.close_camera_stream()
        self._write("Viewport stopped")

    def save_image(self):
        if self.last_frame is None:
            self._write("Save failed: no image available")
            return

        os.makedirs(SHARED_CAPTURE_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"camera_capture_{timestamp}.png"
        full_path = os.path.join(SHARED_CAPTURE_DIR, file_name)
        if cv2.imwrite(full_path, self.last_frame):
            self._write(f"Image saved: {full_path}")
        else:
            self._write("Save failed: cv2.imwrite returned False")

    def find_distance(self):
        try:
            distance = self.cv_manager.find_distance()
            self._write(f"Detected laser distance: {distance}")
        except Exception as exc:
            self._write(f"Distance calc failed: {exc}")
