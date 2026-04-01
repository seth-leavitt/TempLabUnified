import os
import queue
import threading
import tkinter as tk
from datetime import datetime

import cv2
from PIL import Image, ImageTk

from src.cv import CVManager


# Shared output directory used by both TempLab modules.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SHARED_CAPTURE_DIR = os.path.join(PROJECT_ROOT, "shared", "camera_captures")


class CVTab:
    """Tkinter tab that launches and controls a dedicated camera viewport window."""

    def __init__(self, parent):
        self.parent = parent
        self.cv_manager = CVManager()

        # Viewport loop state.
        self.viewport_running = False
        self.viewport_job = None
        self.target_interval_ms = 33
        self.capture_thread = None
        self.capture_stop_event = threading.Event()
        self.frame_queue = queue.Queue(maxsize=2)

        # Cached image objects to avoid garbage collection and redundant conversions.
        self.current_image = None
        self.last_frame = None

        # Window/UI object references populated when camera window is created.
        self.camera_window = None
        self.viewport_label = None
        self.status_label = None
        self.start_viewport_btn = None
        self.stop_viewport_btn = None
        self.capture_btn = None
        self.distance_btn = None
        self.save_btn = None
        self.exposure_input = None
        self.fps_input = None

        self.setup_ui()

    def setup_ui(self):
        """Create the lightweight controls embedded in the main automation GUI."""
        controls = tk.Frame(self.parent)
        controls.pack(fill="x", padx=10, pady=10)

        # Camera launch is separate so the heavy viewport only exists when needed.
        self.connect_btn = tk.Button(controls, text="Connect Camera", command=self.connect_camera)
        self.connect_btn.pack(padx=10, pady=10)

        # Log panel keeps operators informed about camera state and save locations.
        self.output = tk.Text(self.parent, height=10, font=("Arial", 14))
        self.output.pack(fill="both", expand=True, padx=10, pady=10)

    def _write(self, message):
        """Append one status line to the tab log."""
        self.output.insert(tk.END, f"{message}\n")
        self.output.see(tk.END)

    def connect_camera(self):
        """Connect to camera, open viewport window, and start live preview."""
        try:
            self.cv_manager.initialize_camera_stream()
            self._open_camera_window()
            self.start_viewport()
            self._write("Camera stream initialized")
        except Exception as exc:
            self._write(f"Camera init failed: {exc}")

    def _open_camera_window(self):
        """Create or focus the dedicated camera viewport window."""
        if self.camera_window is not None and self.camera_window.winfo_exists():
            self.camera_window.lift()
            return

        self.camera_window = tk.Toplevel(self.parent)
        self.camera_window.title("TempLab Camera Viewport")
        self.camera_window.geometry("1280x860")

        # Two-column layout: viewport on left, controls on right.
        root = tk.Frame(self.camera_window)
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(0, weight=5)
        root.grid_columnconfigure(1, weight=2)
        root.grid_rowconfigure(0, weight=1)

        viewport_frame = tk.Frame(root)
        viewport_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        viewport_frame.grid_rowconfigure(0, weight=1)
        viewport_frame.grid_columnconfigure(0, weight=1)

        controls_frame = tk.Frame(root, bd=1, relief=tk.GROOVE)
        controls_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        controls_frame.grid_columnconfigure(0, weight=1)

        self.viewport_label = tk.Label(
            viewport_frame,
            text="Starting camera viewport...",
            bg="black",
            fg="white",
            anchor="center",
        )
        self.viewport_label.grid(row=0, column=0, sticky="nsew")
        self.viewport_label.bind("<Configure>", self._on_viewport_resize)

        tk.Label(controls_frame, text="Camera Controls", font=("Arial", 14, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 6)
        )

        tk.Label(controls_frame, text="Exposure (us)").grid(row=1, column=0, sticky="w", padx=10, pady=(6, 2))
        self.exposure_input = tk.Entry(controls_frame)
        self.exposure_input.grid(row=2, column=0, sticky="ew", padx=10)
        self.exposure_input.insert(0, str(self.cv_manager.exposure_us))

        apply_exposure_btn = tk.Button(controls_frame, text="Apply Exposure", command=self.apply_exposure)
        apply_exposure_btn.grid(row=3, column=0, sticky="ew", padx=10, pady=(6, 10))

        # Preview FPS controls reduce UI load on lower-power machines.
        tk.Label(controls_frame, text="Preview FPS").grid(row=4, column=0, sticky="w", padx=10, pady=(6, 2))
        self.fps_input = tk.Entry(controls_frame)
        self.fps_input.grid(row=5, column=0, sticky="ew", padx=10)
        self.fps_input.insert(0, "30")
        apply_fps_btn = tk.Button(controls_frame, text="Apply Preview FPS", command=self.apply_preview_fps)
        apply_fps_btn.grid(row=6, column=0, sticky="ew", padx=10, pady=(6, 10))

        self.capture_btn = tk.Button(controls_frame, text="Capture Frame", command=self.capture_frame)
        self.capture_btn.grid(row=7, column=0, sticky="ew", padx=10, pady=4)

        self.start_viewport_btn = tk.Button(controls_frame, text="Start Viewport", command=self.start_viewport)
        self.start_viewport_btn.grid(row=8, column=0, sticky="ew", padx=10, pady=4)

        self.stop_viewport_btn = tk.Button(
            controls_frame,
            text="Stop Viewport",
            command=self.stop_viewport,
            state=tk.DISABLED,
        )
        self.stop_viewport_btn.grid(row=9, column=0, sticky="ew", padx=10, pady=4)

        self.distance_btn = tk.Button(controls_frame, text="Find Laser Distance", command=self.find_distance)
        self.distance_btn.grid(row=10, column=0, sticky="ew", padx=10, pady=4)

        save_btn = tk.Button(controls_frame, text="Save Image", command=self.save_image)
        save_btn.grid(row=11, column=0, sticky="ew", padx=10, pady=4)
        self.save_btn = save_btn

        self.status_label = tk.Label(controls_frame, text="Status: idle", anchor="w", justify=tk.LEFT)
        self.status_label.grid(row=12, column=0, sticky="ew", padx=10, pady=(12, 10))

        self.camera_window.protocol("WM_DELETE_WINDOW", self._on_camera_window_close)

    def _set_status(self, message):
        """Update status line in the camera window and write to tab output."""
        if self.status_label is not None:
            self.status_label.config(text=f"Status: {message}")
        self._write(message)

    def _on_camera_window_close(self):
        """Ensure viewport loop and camera stream are closed with the window."""
        self.stop_viewport(close_stream=True)
        if self.camera_window is not None:
            self.camera_window.destroy()
        self.camera_window = None
        self.viewport_label = None
        self.status_label = None
        self.capture_thread = None
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

    def apply_exposure(self):
        """Apply operator-entered exposure value in microseconds."""
        try:
            exposure_text = self.exposure_input.get().strip() if self.exposure_input is not None else ""
            self.cv_manager.set_exposure(exposure_text)
            self._set_status(f"Exposure set to {self.cv_manager.exposure_us} us")
        except Exception as exc:
            self._set_status(f"Exposure update failed: {exc}")

    def apply_preview_fps(self):
        """Adjust viewport refresh interval without restarting the camera stream."""
        try:
            fps_text = self.fps_input.get().strip() if self.fps_input is not None else ""
            fps = int(float(fps_text))
            if fps <= 0:
                raise ValueError("FPS must be positive")
            self.target_interval_ms = max(1, int(1000 / fps))
            self._set_status(f"Preview FPS set to {fps}")
        except Exception as exc:
            self._set_status(f"Preview FPS update failed: {exc}")

    def capture_frame(self):
        """Capture one frame, cache it, and render immediately."""
        try:
            image = self.cv_manager.capture_image()
            self.last_frame = image
            self._update_viewport(image)
            shape = getattr(image, "shape", None)
            self._set_status(f"Captured image: shape={shape}")
        except Exception as exc:
            self._set_status(f"Capture failed: {exc}")

    def _on_viewport_resize(self, _event):
        """Re-render current frame to fill viewport when window dimensions change."""
        if self.last_frame is not None:
            self._update_viewport(self.last_frame)

    def _capture_worker(self):
        """Continuously capture frames and keep only the newest ones."""
        while not self.capture_stop_event.is_set():
            try:
                frame = self.cv_manager.capture_image()
            except Exception:
                break

            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.frame_queue.put_nowait(frame)
                except queue.Full:
                    pass

    def _update_viewport(self, frame):
        """Convert BGR frame to Tk image and display with lightweight scaling."""
        if frame is None or self.viewport_label is None:
            return

        viewport_w = max(1, self.viewport_label.winfo_width())
        viewport_h = max(1, self.viewport_label.winfo_height())
        target_size = (viewport_w, viewport_h)

        if len(frame.shape) == 2:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        else:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        frame_h, frame_w = rgb_frame.shape[:2]
        scale = min(viewport_w / frame_w, viewport_h / frame_h)
        new_w = max(1, int(frame_w * scale))
        new_h = max(1, int(frame_h * scale))
        resized = cv2.resize(rgb_frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        image = Image.fromarray(resized)
        self.current_image = ImageTk.PhotoImage(image=image)
        self.viewport_label.config(image=self.current_image, text="")
        self.last_rendered_size = target_size

    def _viewport_tick(self):
        """Continuous live-preview loop using Tk's scheduler."""
        if not self.viewport_running:
            return

        try:
            newest_frame = None
            while True:
                newest_frame = self.frame_queue.get_nowait()
        except queue.Empty:
            newest_frame = None
        except Exception as exc:
            self._set_status(f"Viewport update failed: {exc}")
            self.stop_viewport()
            return

        try:
            if newest_frame is not None:
                self.last_frame = newest_frame
                self._update_viewport(newest_frame)
        except Exception as exc:
            self._set_status(f"Viewport update failed: {exc}")
            self.stop_viewport()
            return

        self.viewport_job = self.parent.after(self.target_interval_ms, self._viewport_tick)

    def start_viewport(self):
        """Start periodic camera preview updates."""
        if self.viewport_running:
            return
        if self.camera_window is None or not self.camera_window.winfo_exists():
            self._open_camera_window()

        try:
            self.cv_manager.initialize_camera_stream()
            self.viewport_running = True
            if self.start_viewport_btn is not None:
                self.start_viewport_btn.config(state=tk.DISABLED)
            if self.stop_viewport_btn is not None:
                self.stop_viewport_btn.config(state=tk.NORMAL)
            self._set_status("Viewport started")

            self.capture_stop_event.clear()
            self.capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
            self.capture_thread.start()

            self._viewport_tick()
        except Exception as exc:
            self._set_status(f"Viewport start failed: {exc}")

    def stop_viewport(self, close_stream=True):
        """Stop preview loop and optionally close the underlying camera stream."""
        self.viewport_running = False
        if self.viewport_job is not None:
            self.parent.after_cancel(self.viewport_job)
            self.viewport_job = None
        if self.start_viewport_btn is not None:
            self.start_viewport_btn.config(state=tk.NORMAL)
        if self.stop_viewport_btn is not None:
            self.stop_viewport_btn.config(state=tk.DISABLED)

        self.capture_stop_event.set()
        if self.capture_thread is not None and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
        self.capture_thread = None

        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

        if close_stream:
            self.cv_manager.close_camera_stream()
        self._set_status("Viewport stopped")

    def save_image(self):
        """Save the latest available frame to the shared capture directory."""
        if self.last_frame is None:
            self._set_status("Save failed: no image available")
            return

        os.makedirs(SHARED_CAPTURE_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"camera_capture_{timestamp}.png"
        full_path = os.path.join(SHARED_CAPTURE_DIR, file_name)

        if cv2.imwrite(full_path, self.last_frame):
            self._set_status(f"Image saved: {full_path}")
        else:
            self._set_status("Save failed: cv2.imwrite returned False")

    def find_distance(self):
        """Run laser detection and log the measured pixel distance."""
        try:
            if self.last_frame is None:
                self._set_status("Distance calc failed: no frame available")
                return
            distance = self.cv_manager.find_distance_from_frame(self.last_frame)
            self._set_status(f"Detected laser distance: {distance}")
        except Exception as exc:
            self._set_status(f"Distance calc failed: {exc}")
