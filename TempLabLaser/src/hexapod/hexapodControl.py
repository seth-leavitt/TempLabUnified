import src.hexapod.SYM_HexaPy as SYM_HexaPy
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import re

# TODO:
# - Research the API and how to use it
# - Move in Z direction (Z is the direciton of the lasers)
# - Move in X and Y for rastering
# - Rotation about a point


class HexapodControl():
    ssh_API = None

    def __init__(self):
        self.connectHexapod()
    
    def connectHexapod(self):
        # ip = "192.168.56.101"
        ip = "192.168.16.220"

        SEQ_file_path = "Gamme_PUNA.txt"
        SEQ_pause_stab = 0.1
        SEQ_pause_mes = 0.2
        SEQ_dec_nb = 1
        SEQ_cycle_nb = 2

        verbose = False
        log = True

        # Connect the SSH client
        self.ssh_API = SYM_HexaPy.API()
        self.ssh_API.connect(ip, verbose, log)
        if self.ssh_API.ssh_obj.connected is True:
            print("Connected to the Hexapod")

    def _parse_state(self, state_str):
        """Parse STATE output into a key/value dict."""
        status = {}
        lines = str(state_str).strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip()
            try:
                if re.search(r"[.eE]", val):
                    status[key] = float(val)
                else:
                    status[key] = int(val)
            except Exception:
                status[key] = val
        return status

    def get_translation_position(self):
        """Return current (tx, ty, tz) in mm when available."""
        if self.ssh_API is None:
            return None
        try:
            if hasattr(self.ssh_API, "STATE"):
                raw_state = self.ssh_API.STATE()
            else:
                raw_state = self.ssh_API.SendCommand("STATE")
            status = self._parse_state(raw_state)
            tx = float(status.get("s_mtp_tx", status.get("s_uto_tx")))
            ty = float(status.get("s_mtp_ty", status.get("s_uto_ty")))
            tz = float(status.get("s_mtp_tz", status.get("s_uto_tz")))
            return tx, ty, tz
        except Exception:
            return None
        

    def home(self):
        answer = int(self.ssh_API.SendCommand("HOME").strip())
        print(f"This is the code for the home command: {self.ssh_API.CommandReturns[answer]}")
        return answer
    
    def controlOn(self):
        answer = self.ssh_API.SendCommand("CONTROLON")
        answer = int(answer.strip())
        print(f"This is the code for the control on command: {self.ssh_API.CommandReturns[answer]}")
        if self.ssh_API.CommandReturns[answer]:
            answer = self.ssh_API.CommandReturns[answer]
        elif self.ssh_API.ErrorCodes[answer]:
            answer = self.ssh_API.ErrorCodes[answer]
        return answer

    def moveUp(self, step):
        answer = self.ssh_API.SendCommand("MOVE_PTP", [2.0, float(step), 0.0, 0.0, 0.0, 0.0, 0.0])
        answer = int(answer.strip())
        if answer in self.ssh_API.CommandReturns.keys():
            answer = self.ssh_API.CommandReturns[answer]
        elif answer in self.ssh_API.ErrorCodes.keys():
            answer = self.ssh_API.ErrorCodes[answer]
        return answer
    def moveDown(self, step):
        answer = self.ssh_API.SendCommand("MOVE_PTP", [2.0, -float(step), 0.0, 0.0, 0.0, 0.0, 0.0])
        answer = int(answer.strip())
        if answer in self.ssh_API.CommandReturns.keys():
            answer = self.ssh_API.CommandReturns[answer]
        elif answer in self.ssh_API.ErrorCodes.keys():
            answer = self.ssh_API.ErrorCodes[answer]
        return answer
    def moveLeft(self, step):
        answer = self.ssh_API.SendCommand("MOVE_PTP", [2.0, 0.0, float(step), 0.0, 0.0, 0.0, 0.0])
        answer = int(answer.strip())
        if answer in self.ssh_API.CommandReturns.keys():
            answer = self.ssh_API.CommandReturns[answer]
        elif answer in self.ssh_API.ErrorCodes.keys():
            answer = self.ssh_API.ErrorCodes[answer]
        return answer
    def moveRight(self, step):
        answer = self.ssh_API.SendCommand("MOVE_PTP", [2.0, 0.0, -float(step), 0.0, 0.0, 0.0, 0.0])
        answer = int(answer.strip())
        if answer in self.ssh_API.CommandReturns.keys():
            answer = self.ssh_API.CommandReturns[answer]
        elif answer in self.ssh_API.ErrorCodes.keys():
            answer = self.ssh_API.ErrorCodes[answer]
        return answer 
    def moveOut(self, step):
        answer = self.ssh_API.SendCommand("MOVE_PTP", [2.0, 0.0, 0.0, float(step), 0.0, 0.0, 0.0])
        answer = int(answer.strip())
        if answer in self.ssh_API.CommandReturns.keys():
            answer = self.ssh_API.CommandReturns[answer]
        elif answer in self.ssh_API.ErrorCodes.keys():
            answer = self.ssh_API.ErrorCodes[answer]
        return answer
    def moveIn(self, step):
        answer = self.ssh_API.SendCommand("MOVE_PTP", [2.0, 0.0, 0.0, -float(step), 0.0, 0.0, 0.0])
        answer = int(answer.strip())
        if answer in self.ssh_API.CommandReturns.keys():
            answer = self.ssh_API.CommandReturns[answer]
        elif answer in self.ssh_API.ErrorCodes.keys():
            answer = self.ssh_API.ErrorCodes[answer]
        return answer
    def setSpeed(self, speed):
        answer = self.ssh_API.SendCommand("CFG_SPEED", [0.0, float(speed)]) #arguments: translationSpeed angularSpeed
        answer = int(answer.strip())
        if answer in self.ssh_API.CommandReturns.keys():
            answer = self.ssh_API.CommandReturns[answer]
        elif answer in self.ssh_API.ErrorCodes.keys():
            answer = self.ssh_API.ErrorCodes[answer]
        return answer
    def resetPosition(self):
        answer = self.ssh_API.SendCommand("MOVE_SPECIFICPOS", [3.0])
        answer = int(answer.strip())
        if answer in self.ssh_API.CommandReturns.keys():
            answer = self.ssh_API.CommandReturns[answer]
        elif answer in self.ssh_API.ErrorCodes.keys():
            answer = self.ssh_API.ErrorCodes[answer]
        return answer 
        

  
