# Network Planner

## Project Purpose
Network Planner is a short-term research desktop tool for interactively planning ns-3 Wi-Fi 7 scenarios. Phase A focuses on the GUI interaction foundation only: placing devices on a 2D scene, editing their basic properties, and saving/loading the scenario state.

## Folder Structure
```text
Network-Planner/
  main.py
  app.py
  requirements.txt
  README.md
  models/
  services/
  graphics/
  ui/
  storage/
  adapters/
```

## Create a Virtual Environment
### PowerShell
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## Install Dependencies
```powershell
pip install -r requirements.txt
```

## Run the App
```powershell
python main.py
```

## Current Phase A Scope
- PySide6 desktop application bootstrap
- Main window with left palette, center canvas, right property panel, and status bar
- 2D scene with world coordinates in meters
- Bottom-left origin with Y axis increasing upward
- Grid and coordinate reference
- AP and STA device placement
- Click-add at viewport center
- Drag-drop onto the canvas
- Device selection, dragging, keyboard fine-tuning, and Delete removal
- Device basic property editing
- JSON save/load with a root `schema_version`

## Placeholder For Phase B
- Wi-Fi and link metrics
- Relations table live calculations
- ns-3 export implementation
- Advanced environment modeling
- Simulation-derived summaries and validation

## Phase A Manual Validation Checklist
- Palette click-add: click `Add AP` and `Add STA`, confirm new devices appear at the current viewport center.
- Palette drag-drop: drag AP/STA from the palette into the canvas and confirm the device is placed at the drop location.
- Selection and property binding: select a device, confirm the `Device Basic` tab updates, then rename or edit coordinates and confirm the canvas updates.
- Keyboard nudging: with a device selected, test `Arrow`, `Shift + Arrow`, and `Ctrl + Arrow`.
- Delete selected device: select a device, press `Delete`, and confirm the item, property panel state, and status bar selection update correctly.
- Zoom and pan: test `Ctrl + mouse wheel` for zoom and middle mouse drag for pan; plain wheel should keep normal scrolling behavior.
- Save/load JSON: save a scenario, reload it, and confirm devices and names are restored correctly.
- Bottom-left origin and Y-up: move a device upward on screen and confirm its world Y value increases; verify `(0,0)` is the bottom-left world origin.
