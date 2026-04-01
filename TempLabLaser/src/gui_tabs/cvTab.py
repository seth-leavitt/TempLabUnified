import tkinter as tk

from src.cv import CVManager


class CVTab:
    def __init__(self, parent):
        self.parent = parent
        self.cv_manager = CVManager()
        self.setup_ui()

    def setup_ui(self):
        self.connect_btn = tk.Button(self.parent, text="Connect Camera", command=self.connect_camera)
        self.connect_btn.pack(padx=10, pady=10)

        self.capture_btn = tk.Button(self.parent, text="Capture Frame", command=self.capture_frame)
        self.capture_btn.pack(padx=10, pady=10)

        self.distance_btn = tk.Button(self.parent, text="Find Laser Distance", command=self.find_distance)
        self.distance_btn.pack(padx=10, pady=10)

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
            shape = getattr(image, "shape", None)
            self._write(f"Captured image: shape={shape}")
        except Exception as exc:
            self._write(f"Capture failed: {exc}")

    def find_distance(self):
        try:
            distance = self.cv_manager.find_distance()
            self._write(f"Detected laser distance: {distance}")
        except Exception as exc:
            self._write(f"Distance calc failed: {exc}")
