# Network Planner

## Project Purpose
Network Planner is a desktop research tool for interactively planning ns-3 Wi-Fi scenarios.
It lets you place APs and STAs on a 2D canvas, configure wireless parameters, and instantly see
link-level relations (distance, path loss, RSSI, SNR) for the selected device.
The scenario is stored as JSON and is designed to feed an ns-3 export adapter in a later phase.

---

## Folder Structure
```text
Network-Planner/
  main.py               — entry point
  app.py                — dependency wiring
  requirements.txt
  models/               — pure data models (no Qt)
  services/             — business logic and calculation services
  graphics/             — PySide6 canvas items and scene
  ui/                   — Qt widgets, panels, and tabs
  storage/              — JSON DTO and repository
  adapters/             — ns-3 export (Phase C skeleton)
  tests/                — unittest suite
  docs/                 — handoff documents
  .claude_project/      — agent plan and decision log
```

---

## Setup

### PowerShell
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Build EXE (Windows)
```powershell
.\build.ps1
```

Output layout:
- `bin/NetworkPlanner.exe`
- `bin/lib/*`

---

## Automated Tests
```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
Tests cover: propagation calculator, relation calculation service, schema v1/v2 round-trip.
