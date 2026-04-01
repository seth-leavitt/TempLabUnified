import tkinter as tk
from tkinter import ttk

from src.hexapod.hexapodControl import HexapodControl


class HexapodTab:
    # Software travel estimate in mm from the current origin in each translation axis.
    # The UI uses this to display remaining travel in each direction.
    AXIS_TRAVEL_LIMIT_MM = 30.0

    def __init__(self, parent):
        self.parent = parent
        self.translation_position = {"up": 0.0, "left": 0.0, "out": 0.0}
        self.remaining_labels = {}
        self.remaining_bars = {}
        self.hardware_poll_job = None
        self.setup_ui()
        self.hexapod = None

    def setup_ui(self):
        hexapodTab = self.parent
        self.connectBtn = tk.Button(hexapodTab, text="Connect to Hexapod", command=self.connect_hexapod)
        self.connectBtn.pack(padx=10, pady=10)
        self.homeBtn = tk.Button(hexapodTab, text="Home Hexapod", command=self.home_hexapod)
        self.homeBtn.pack(padx=10, pady=10)
        self.controlOnBtn = tk.Button(hexapodTab, text="Turn on Control (Press this after homing)",
                                      command=self.control_on_hexapod)
        self.controlOnBtn.pack(padx=10, pady=10)
        self.stepLabel = tk.Label(hexapodTab, text="Step Size (mm)")
        self.stepLabel.pack(padx=10, pady=5)
        self.stepInput = tk.Entry(hexapodTab)
        self.stepInput.pack(padx=10, pady=10)
        self.resetBtn = tk.Button(hexapodTab, text="Reset Position", command=self.reset_position)
        self.resetBtn.pack(padx=10, pady=10)

        remaining_frame = ttk.LabelFrame(hexapodTab, text="Remaining Travel (mm)")
        remaining_frame.pack(fill='x', padx=20, pady=10)
        directions = ["Up", "Down", "Left", "Right", "In", "Out"]
        for row, direction in enumerate(directions):
            ttk.Label(remaining_frame, text=direction, width=10).grid(row=row, column=0, padx=8, pady=4, sticky=tk.W)
            bar = ttk.Progressbar(
                remaining_frame,
                orient=tk.HORIZONTAL,
                mode='determinate',
                length=220,
                maximum=self.AXIS_TRAVEL_LIMIT_MM,
            )
            bar.grid(row=row, column=1, padx=8, pady=4, sticky=tk.W + tk.E)
            value_label = ttk.Label(remaining_frame, text="0.00 mm", width=12)
            value_label.grid(row=row, column=2, padx=8, pady=4, sticky=tk.E)
            self.remaining_bars[direction.lower()] = bar
            self.remaining_labels[direction.lower()] = value_label
        self._refresh_remaining_travel_ui()

        bfTranslation = tk.Frame(hexapodTab)
        bfTranslation.columnconfigure(0, weight=1)
        bfTranslation.columnconfigure(1, weight=1)
        bfTranslation.columnconfigure(2, weight=1)
        bfTranslation.rowconfigure(0, weight=1)
        bfTranslation.rowconfigure(1, weight=1)
        bfTranslation.rowconfigure(2, weight=1)

        btn_up = tk.Button(bfTranslation, text="Up", command=self.move_up, font=('Arial', 18))
        btn_up.grid(row=0, column=1, sticky=tk.W + tk.E)

        btn_left = tk.Button(bfTranslation, text="Left", command=self.move_left, font=('Arial', 18))
        btn_left.grid(row=1, column=0, sticky=tk.W + tk.E)

        btn_down = tk.Button(bfTranslation, text="Down", command=self.move_down, font=('Arial', 18))
        btn_down.grid(row=1, column=1, sticky=tk.W + tk.E)

        btn_right = tk.Button(bfTranslation, text="Right", command=self.move_right, font=('Arial', 18))
        btn_right.grid(row=1, column=2, sticky=tk.W + tk.E)

        btn_in = tk.Button(bfTranslation, text="In", command=self.move_in, font=('Arial', 18))
        btn_in.grid(row=2, column=1, sticky=tk.W + tk.E)

        btn_out = tk.Button(bfTranslation, text="Out", command=self.move_out, font=('Arial', 18))
        btn_out.grid(row=3, column=1, sticky=tk.W + tk.E)

        bfTranslation.pack(fill='x', padx=20, pady=20)

        self.hexapodTextbox = tk.Text(hexapodTab, height=8, font=('Arial', 16))
        self.hexapodTextbox.pack(padx=10, pady=10)

    def connect_hexapod(self):
        try:
            self.hexapod = HexapodControl()
            self.hexapodTextbox.insert(tk.END, "Connected to hexapod.\n")
            self._reset_translation_estimate()
            self._sync_translation_from_hardware()
            self._schedule_hardware_poll()
        except Exception as e:
            self.hexapodTextbox.insert(tk.END, "Unable to connect to hexapod.\n Error: " + str(e) + "\n")

    def _is_connected(self):
        return self.hexapod is not None and getattr(self.hexapod, "ssh_API", None) is not None

    def _parse_step(self):
        try:
            return float(self.stepInput.get())
        except Exception:
            self.hexapodTextbox.insert(tk.END, "Invalid step size. Enter a numeric value in mm.\n")
            return None

    def _reset_translation_estimate(self):
        self.translation_position = {"up": 0.0, "left": 0.0, "out": 0.0}
        self._refresh_remaining_travel_ui()

    def _refresh_remaining_travel_ui(self):
        up_remaining = max(0.0, self.AXIS_TRAVEL_LIMIT_MM - self.translation_position["up"])
        down_remaining = max(0.0, self.AXIS_TRAVEL_LIMIT_MM + self.translation_position["up"])
        left_remaining = max(0.0, self.AXIS_TRAVEL_LIMIT_MM - self.translation_position["left"])
        right_remaining = max(0.0, self.AXIS_TRAVEL_LIMIT_MM + self.translation_position["left"])
        out_remaining = max(0.0, self.AXIS_TRAVEL_LIMIT_MM - self.translation_position["out"])
        in_remaining = max(0.0, self.AXIS_TRAVEL_LIMIT_MM + self.translation_position["out"])

        values = {
            "up": up_remaining,
            "down": down_remaining,
            "left": left_remaining,
            "right": right_remaining,
            "in": in_remaining,
            "out": out_remaining,
        }

        for direction, value in values.items():
            if direction in self.remaining_bars:
                self.remaining_bars[direction]["value"] = value
            if direction in self.remaining_labels:
                self.remaining_labels[direction].config(text=f"{value:.2f} mm")

    def _sync_translation_from_hardware(self):
        """Refresh translation estimate from live hexapod position when possible."""
        if not self._is_connected():
            return False
        try:
            position = self.hexapod.get_translation_position()
        except Exception:
            return False
        if not position:
            return False

        tx, ty, tz = position
        self.translation_position["up"] = max(-self.AXIS_TRAVEL_LIMIT_MM, min(self.AXIS_TRAVEL_LIMIT_MM, float(tx)))
        self.translation_position["left"] = max(-self.AXIS_TRAVEL_LIMIT_MM, min(self.AXIS_TRAVEL_LIMIT_MM, float(ty)))
        self.translation_position["out"] = max(-self.AXIS_TRAVEL_LIMIT_MM, min(self.AXIS_TRAVEL_LIMIT_MM, float(tz)))
        self._refresh_remaining_travel_ui()
        return True

    def _schedule_hardware_poll(self):
        if self.hardware_poll_job is not None:
            self.parent.after_cancel(self.hardware_poll_job)
            self.hardware_poll_job = None

        def poll_once():
            if self._is_connected():
                self._sync_translation_from_hardware()
                self.hardware_poll_job = self.parent.after(800, poll_once)
            else:
                self.hardware_poll_job = None

        self.hardware_poll_job = self.parent.after(800, poll_once)

    def _apply_move_estimate(self, up_delta=0.0, left_delta=0.0, out_delta=0.0):
        # Update immediately for operator feedback, then allow hardware sync to correct drift.
        self.translation_position["up"] = max(
            -self.AXIS_TRAVEL_LIMIT_MM,
            min(self.AXIS_TRAVEL_LIMIT_MM, self.translation_position["up"] + up_delta),
        )
        self.translation_position["left"] = max(
            -self.AXIS_TRAVEL_LIMIT_MM,
            min(self.AXIS_TRAVEL_LIMIT_MM, self.translation_position["left"] + left_delta),
        )
        self.translation_position["out"] = max(
            -self.AXIS_TRAVEL_LIMIT_MM,
            min(self.AXIS_TRAVEL_LIMIT_MM, self.translation_position["out"] + out_delta),
        )
        self._refresh_remaining_travel_ui()
        # Non-blocking correction from live position when available.
        self.parent.after(50, self._sync_translation_from_hardware)

    def home_hexapod(self):
        if not self._is_connected():
            print("Not connected to hexapod")
        else:
            response = self.hexapod.home()
            self.hexapodTextbox.insert(tk.END, f"Home: {response}\n")
            if not self._sync_translation_from_hardware():
                self._reset_translation_estimate()

    def control_on_hexapod(self):
        if not self._is_connected():
            print("Not connected to hexapod")
        else:
            response = self.hexapod.controlOn()
            self.hexapodTextbox.insert(tk.END, f"Control on: {response}\n")

    def move_up(self):
        if not self._is_connected():
            print("Not connected to hexapod")
        else:
            step = self._parse_step()
            if step is None:
                return
            response = self.hexapod.moveUp(step)
            self.hexapodTextbox.insert(tk.END, f"Move up: {response}\n")
            self._apply_move_estimate(up_delta=step)

    def move_down(self):
        if not self._is_connected():
            print("Move Down")
        else:
            step = self._parse_step()
            if step is None:
                return
            response = self.hexapod.moveDown(step)
            self.hexapodTextbox.insert(tk.END, f"Move down: {response}\n")
            self._apply_move_estimate(up_delta=-step)

    def move_left(self):
        if not self._is_connected():
            print("Move Left")
        else:
            step = self._parse_step()
            if step is None:
                return
            response = self.hexapod.moveLeft(step)
            self.hexapodTextbox.insert(tk.END, f"Move left: {response}\n")
            self._apply_move_estimate(left_delta=step)

    def move_right(self):
        if not self._is_connected():
            print("Move Right")
        else:
            step = self._parse_step()
            if step is None:
                return
            response = self.hexapod.moveRight(step)
            self.hexapodTextbox.insert(tk.END, f"Move right: {response}\n")
            self._apply_move_estimate(left_delta=-step)

    def move_in(self):
        if not self._is_connected():
            print("Move In")
        else:
            step = self._parse_step()
            if step is None:
                return
            response = self.hexapod.moveIn(step)
            self.hexapodTextbox.insert(tk.END, f"Move in: {response}\n")
            self._apply_move_estimate(out_delta=-step)

    def move_out(self):
        if not self._is_connected():
            print("Move Out")
        else:
            step = self._parse_step()
            if step is None:
                return
            response = self.hexapod.moveOut(step)
            self.hexapodTextbox.insert(tk.END, f"Move out: {response}\n")
            self._apply_move_estimate(out_delta=step)

    def reset_position(self):
        if not self._is_connected():
            print("Reset Position")
        else:
            response = self.hexapod.resetPosition()
            self.hexapodTextbox.insert(tk.END, f"Reset Position: {response}\n")
            if not self._sync_translation_from_hardware():
                self._reset_translation_estimate()
