# TempLab Unified

This repository combines the two TempLab packages into one working tree:

- `TempLabLaser/`: microscope and hardware automation GUI
- `TempLab-CV/`: computer vision and laser detection package

## Initial integration state

- TempLab Laser includes the fiducial work by merging `origin/Rastering-Fiducial` before import.
- A first-pass CV integration has been added directly into the laser GUI as a new `Computer Vision` tab.
- Shared CV code now lives under `TempLabLaser/src/cv/`.

## Run

```bash
python TempLabLaser/main.py
```
