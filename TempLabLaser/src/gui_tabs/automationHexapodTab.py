import tkinter as tk
import tkinter.filedialog
from tkinter import ttk
import ttkbootstrap as ttk
import numpy as np
import threading
from src.hexapod.hexapodControl2 import HexapodControl
import regex as re


class HexapodAutomationTab:
    def __init__(self, parent, instruments, main_gui):
        self.parent = parent
        self.instruments = instruments
        self.hexapod = None
        self.degrees_of_sweep = tk.StringVar()
        self.stepCount = tk.IntVar(value=20)  # Default step count
        self.hexapodCenter = tk.StringVar(value="0")  # Default center position
        self.pumpLaser = tk.StringVar(value="0")  # Default pump laser state
        self.state_poll_inflight = False
        self.latest_pose = {
            'X': 0.0,
            'Y': 0.0,
            'Z': 0.0,
            'Roll (Rx)': 0.0,
            'Pitch (Ry)': 0.0,
            'Yaw (Rz)': 0.0,
        }
        self.setup_ui()



    def setup_ui(self):
        # [Previous imports at the top of the file]

        hexapod_automation_tab = self.parent

        # Create main frames
        status_frame = ttk.LabelFrame(hexapod_automation_tab, text="Hexapod Status and Control")
        status_frame.grid(row=0, column=0, columnspan=5, padx=10, pady=5, sticky='nsew')

        movement_frame = ttk.LabelFrame(hexapod_automation_tab, text="Movement Parameters")
        movement_frame.grid(row=1, column=0, columnspan=5, padx=10, pady=5, sticky='nsew')

        adjustment_frame = ttk.LabelFrame(hexapod_automation_tab, text="Manual Adjustment")
        adjustment_frame.grid(row=2, column=0, columnspan=5, padx=10, pady=5, sticky='nsew')

        output_frame = ttk.LabelFrame(hexapod_automation_tab, text="Output and Data")
        output_frame.grid(row=3, column=0, columnspan=5, padx=10, pady=5, sticky='nsew')

        debugging_frame = ttk.LabelFrame(hexapod_automation_tab, text="Debugging Stuff")
        debugging_frame.grid(row=4, column=0, columnspan=5, padx=10, pady=5, sticky='nsew')

        # Add new constraints frame
        constraints_frame = ttk.LabelFrame(hexapod_automation_tab, text="Movement Constraints")
        constraints_frame.grid(row=3, column=0, columnspan=5, padx=10, pady=5, sticky='nsew')

        # Create a subframe for the meters to control their size and layout
        meters_frame = ttk.Frame(constraints_frame)
        meters_frame.grid(row=0, column=0, columnspan=6, padx=5, pady=5)

        # Define coordinate systems with their ranges
        self.coordinates = {
            'X': {'name': 'X Position', 'range': (-30, 30)},  # ±50mm
            'Y': {'name': 'Y Position', 'range': (-30, 30)},  # ±50mm
            'Z': {'name': 'Z Position', 'range': (-20, 20)},  # ±25mm
            'Roll (Rx)': {'name': 'Roll', 'range': (-11, 11)},     # ±20°
            'Pitch (Ry)': {'name': 'Pitch', 'range': (-11, 11)},   # ±20°
            'Yaw (Rz)': {'name': 'Yaw', 'range': (-20, 20)}        # ±20°
        }

        self.constraint_meters = {}

        for i, (coord, info) in enumerate(self.coordinates.items()):
            # Create frame for each meter
            meter_frame = ttk.LabelFrame(meters_frame, text=info['name'])
            meter_frame.grid(row=i//3, column=i%3, padx=5, pady=5)

            # Create meter with small size
            meter = ttk.Meter(
                meter_frame,
                metersize=150,
                padding=5,
                amountused=0,
                amounttotal=100,
                metertype="full",  # Full circle display
                subtext=f"+{info['range'][1]:.1f} / {info['range'][0]:.1f}",
                interactive=False,
                stripethickness=10
            )
            meter.pack(padx=5, pady=5)
            meter.configure(amountused=0)

            # Store meter reference
            self.constraint_meters[coord] = {
                'meter': meter,
                'range': info['range']
            }

        self._apply_pose_to_meters()

        # Method to update meter values

        # Status and Control Section
        self.hexapodStatusLabel = tk.Label(status_frame, text="Hexapod Status: Not Connected")
        self.hexapodStatusLabel.grid(row=0, column=0, columnspan=4, padx=10, pady=5)

        self.connectHexapodButton = tk.Button(status_frame, text="Connect to Hexapod",
                                              command=self.connect_hexapod)
        self.connectHexapodButton.grid(row=1, column=0, padx=10, pady=5)

        self.homeHexapodButton = tk.Button(status_frame, text="Home Hexapod",
                                            command=lambda: self.hexapod.home())
        self.homeHexapodButton.grid(row=1, column=1, padx=10, pady=5)

        self.controlOnHexapodButton = tk.Button(status_frame, text="Turn on Control (Press this after homing)",
                                                command=lambda: self.hexapod.controlOn())
        self.controlOnHexapodButton.grid(row=1, column=2, padx=10, pady=5)

        self.controlOffHexapodButton = tk.Button(status_frame, text="Turn off Control",
                                                 command=lambda: self.hexapod.controlOff())
        self.controlOffHexapodButton.grid(row=1, column=3, padx=10, pady=5)

        # Movement Parameters Section
        self.degreesSweepLabel = tk.Label(movement_frame, text="Degrees of Sweep")
        self.degreesSweepLabel.grid(row=0, column=0, padx=10, pady=5, sticky=tk.E)
        self.degreesSweepInput = tk.Entry(movement_frame, textvariable=self.degrees_of_sweep)
        self.degreesSweepInput.grid(row=0, column=1, padx=10, pady=5)

        self.pumpLaserDistanceLabel = tk.Label(movement_frame, text="Distance between lasers (mm)")
        self.pumpLaserDistanceLabel.grid(row=1, column=0, padx=10, pady=5, sticky=tk.E)
        self.pumpLaserDistanceInput = tk.Entry(movement_frame)
        self.pumpLaserDistanceInput.insert(0, "1.0")
        self.pumpLaserDistanceInput.grid(row=1, column=1, padx=10, pady=5)

        self.stepCountLabel = tk.Label(movement_frame, text="Step Count:")
        self.stepCount = tk.IntVar(movement_frame, 1)
        self.stepCountInput = tk.Entry(movement_frame, textvariable=self.stepCount, state='normal')
        self.stepCountLabel.grid(row=2, column=0, padx=10, pady=5, sticky=tk.E)
        self.stepCountInput.grid(row=2, column=1, padx=10, pady=5)

        # Output and Data Section
        file_frame = ttk.Frame(output_frame)
        file_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=5)

        self.stepFileLocation = tk.StringVar(file_frame, "No Location Given")
        self.stepFileButton = tk.Button(file_frame, text="Choose File Location",
                                        command=self.select_file_location)
        self.stepFileButton.grid(row=0, column=0, padx=10, pady=5)
        
        self.stepFileLabel = tk.Label(file_frame, textvariable=self.stepFileLocation)
        self.stepFileLabel.grid(row=0, column=1, padx=10, pady=5)

        self.automationGraph = tk.Label(output_frame)
        self.automationGraph.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky='nsew')

        # Manual Adjustment Section
        def verify_input(value):
            expression = r"^-?(?:\d+(\.\d*)?|\.\d*)?$"
            if value == "" or re.fullmatch(expression, value):
                return True
            else:
                return False
        vcmd = self.parent.register(verify_input)
                
        self.manualTranslationLabel = tk.Label(adjustment_frame, text="Manual Translation (mm):")
        self.manualTranslationLabel.grid(row=1, column=0, padx=10, pady=5, sticky=tk.E)
        self.manualTranslationX = tk.Entry(adjustment_frame, width=5, validate="all", validatecommand=(vcmd, '%P'))
        self.manualTranslationX.insert(0, "0")
        self.manualTranslationX.grid(row=1, column=1, padx=5, pady=5)
        self.TranslationXLabel = tk.Label(adjustment_frame, text="X")
        self.TranslationXLabel.grid(row=0, column=1, padx=5, pady=5)

        self.manualTranslationY = tk.Entry(adjustment_frame, width=5, validate="all", validatecommand=(vcmd, '%P'))
        self.manualTranslationY.insert(0, "0")
        self.manualTranslationY.grid(row=1, column=2, padx=5, pady=5)
        self.TranslationYLabel = tk.Label(adjustment_frame, text="Y")
        self.TranslationYLabel.grid(row=0, column=2, padx=5, pady=5)


        self.manualTranslationZ = tk.Entry(adjustment_frame, width=5, validate="all", validatecommand=(vcmd, '%P'))
        self.manualTranslationZ.insert(0, "0")
        self.manualTranslationZ.grid(row=1, column=3, padx=5, pady=5)
        self.TranslationZLabel = tk.Label(adjustment_frame, text="Z")
        self.TranslationZLabel.grid(row=0, column=3, padx=5, pady=5)


        self.manualTranslationButton = tk.Button(adjustment_frame, text="Translate",
                                                command=lambda: self.hexapod.translate(
                                                    np.array([
                                                        float(self.manualTranslationX.get()),
                                                        float(self.manualTranslationY.get()),
                                                        float(self.manualTranslationZ.get())
                                                    ])))
        self.manualTranslationButton.grid(row=1, column=4, padx=10, pady=5)
        self.manualTranslationButtonReverse = tk.Button(adjustment_frame, text="Actually go back",
                                                 command=lambda: self.hexapod.translate(
                                                     np.array([
                                                         -float(self.manualTranslationX.get()),
                                                         -float(self.manualTranslationY.get()),
                                                         -float(self.manualTranslationZ.get())
                                                     ])))
        self.manualTranslationButtonReverse.grid(row=1, column=5, padx=10, pady=5)
        self.manualRotationLabel = tk.Label(adjustment_frame, text="Rotation (θ°):")
        self.manualRotationLabel.grid(row=2, column=0, padx=10, pady=5, sticky=tk.E)
        self.manualRotationX = tk.Entry(adjustment_frame, width=5)
        self.manualRotationX.grid(row=2, column=1, padx=5, pady=5)

        self.manualRotationY = tk.Entry(adjustment_frame, width=5)
        self.manualRotationY.grid(row=2, column=2, padx=5, pady=5)

        self.manualRotationZ = tk.Entry(adjustment_frame, width=5)
        self.manualRotationZ.grid(row=2, column=3, padx=5, pady=5)

        self.manualRotationButton = tk.Button(adjustment_frame, text="Rotate",
                                                command=lambda: self.hexapod.rotate(
                                                    np.array([
                                                        float(self.manualRotationY.get()),
                                                        float(self.manualRotationX.get()),
                                                        float(self.manualRotationZ.get())
                                                    ])))
        self.manualRotationButton.grid(row=2, column=4, padx=10, pady=5)

        # Debugging Section
        self.printStateButton = tk.Button(debugging_frame, text="Print Hexapod State",
                                          command=self.print_hexapod_state)
        self.printStateButton.grid(row=0, column=0, padx=10, pady=5)

        # Configure update timer
        self.hexapodStatusLabel.after(100, self.update_hexapod_status)

        # Configure grid weights
        for frame in (status_frame, movement_frame, output_frame):
            frame.grid_columnconfigure(1, weight=1)

    def update_meter_value(self, coordinate, current_value):
        """Update one dial to show remaining positive/negative travel."""
        meter_info = self.constraint_meters[coordinate]
        meter = meter_info['meter']
        min_limit, max_limit = meter_info['range']

        value = max(min_limit, min(max_limit, float(current_value)))
        remaining_pos = max(0.0, max_limit - value)
        remaining_neg = max(0.0, value - min_limit)

        span = max_limit - min_limit
        center = (max_limit + min_limit) / 2.0
        usage_pct = (abs(value - center) / (span / 2.0)) * 100.0 if span > 0 else 0.0

        meter.configure(
            amountused=max(0.0, min(100.0, usage_pct)),
            subtext=f"+{remaining_pos:.2f} / -{remaining_neg:.2f}"
        )

    def _apply_pose_to_meters(self):
        for coordinate, value in self.latest_pose.items():
            if coordinate in self.constraint_meters:
                self.update_meter_value(coordinate, value)

    def _refresh_pose_from_hexapod(self):
        """Poll state in background and update dials on the GUI thread."""
        try:
            if self.hexapod is None:
                return
            self.hexapod.getState()
            status = self.hexapod.status_dict or {}
            pose = {
                'X': float(status.get('s_mtp_tx', status.get('s_uto_tx', self.latest_pose['X']))),
                'Y': float(status.get('s_mtp_ty', status.get('s_uto_ty', self.latest_pose['Y']))),
                'Z': float(status.get('s_mtp_tz', status.get('s_uto_tz', self.latest_pose['Z']))),
                'Roll (Rx)': float(status.get('s_mtp_rx', status.get('s_uto_rx', self.latest_pose['Roll (Rx)']))),
                'Pitch (Ry)': float(status.get('s_mtp_ry', status.get('s_uto_ry', self.latest_pose['Pitch (Ry)']))),
                'Yaw (Rz)': float(status.get('s_mtp_rz', status.get('s_uto_rz', self.latest_pose['Yaw (Rz)']))),
            }
            self.parent.after(0, lambda: self._set_latest_pose(pose))
        except Exception:
            pass
        finally:
            self.parent.after(0, lambda: setattr(self, 'state_poll_inflight', False))

    def _set_latest_pose(self, pose):
        self.latest_pose.update(pose)
        self._apply_pose_to_meters()

    def print_hexapod_state(self):
        def actually_print():
            if self.hexapod is not None:
                print(self.hexapod.getState())
            else:
                print("Hexapod is not connected.")
        if self.hexapod is not None:
            # Run the print in a separate thread to avoid blocking the GUI
            threading.Thread(target=actually_print).start()
        else:
            print("Hexapod is not connected.")

    def select_file_location(self):
        filePath = tk.filedialog.askdirectory()
        if filePath == "":
            return None
        else:
            self.stepFileLocation.set(filePath)
            print(self.stepFileLocation)
            return None

    def connect_hexapod(self):
        try:
            self.hexapod = HexapodControl()
            self.hexapod.connectHexapod()
        except Exception as e:
            print(f"Error connecting to Hexapod: {e}")

    def update_hexapod_status(self):
        if self.hexapod is None:
            self.hexapodStatusLabel.config(text="Hexapod Not Connected")
        else:
            try:
                self.hexapodStatusLabel.config(
                    text=f"Hexapod Ready for New Commands: {self.hexapod.ready_for_commands}",
                    fg="green" if self.hexapod.ready_for_commands else "red"
                )
                if not self.state_poll_inflight:
                    self.state_poll_inflight = True
                    threading.Thread(target=self._refresh_pose_from_hexapod, daemon=True).start()
            except Exception as e:
                self.hexapodStatusLabel.config(text=f"Error: {e}")

        # update status and meters on a moderate cadence.
        self.hexapodStatusLabel.after(250, self.update_hexapod_status)
