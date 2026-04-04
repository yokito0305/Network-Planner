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

---

## Phase A — GUI Foundation (complete)
- PySide6 desktop application bootstrap
- Main window: left palette, center canvas, right property panel, status bar
- 2D scene with world coordinates in metres, bottom-left origin, Y-up
- AP and STA device placement (click-add and drag-drop)
- Device selection, dragging, keyboard fine-tuning (`Arrow` / `Shift+Arrow` / `Ctrl+Arrow`), Delete removal
- Device basic property editing (name, position)
- JSON save / load (`schema_version: 1`)
- Adaptive grid with zoom/pan

---

## Phase B — Calculation Layer & UI Vertical Slice (complete)

### New capabilities
- **Wi-Fi / Link tab**: edit TX power (dBm), manage per-device links (name, enabled, band)
- **Environment tab**: edit path-loss exponent, reference distance, noise floor, band profiles (2.4 / 5 / 6 GHz)
- **Relations tab**: live peer summary table + link detail table for the selected device
  - Columns: distance, link count, best RSSI, best SNR, status
  - Per-link: band, selected link name, peer link name, freq (MHz), path loss, RSSI, SNR, status
- Recalculation triggered by: selection change, device move, environment edit, radio/link edit, scenario load
- JSON schema upgraded to **v2** (v1 files still load with synthesised defaults)
- Log-Distance propagation model (path loss, RSSI, SNR)
- Multi-link support per device (same-band enabled pairs only)

### Schema change
`schema_version` is now `2`. Old `v1` files load cleanly; new v2 fields are synthesised from defaults.

---

## Phase B Manual Validation Checklist
Run with `.venv\Scripts\python.exe main.py` on Windows.

1. **App launches** — no errors in console, all four property panel tabs visible
2. **Phase A interactions still work** — add/drag/nudge/delete/zoom/pan/save/load
3. **Select a device** — Wi-Fi tab shows its TX power and links; Relations tab shows peer rows
4. **Move a device** — distance / RSSI / SNR values in Relations tab update live
5. **Edit environment values** — change path-loss exponent → Relations tab values change
6. **Disable a link** — uncheck a link in Wi-Fi tab → that band disappears from Relations tab
7. **Mismatched bands** — if selected device has only 5 GHz enabled but peer only 2.4 GHz, Relations tab shows "No same-band enabled links"
8. **Save / Load v2** — save a scenario, reload it, confirm TX power, links, and environment values are preserved
9. **Load old v1 JSON** — load a Phase A saved file, confirm it opens and Phase B defaults are synthesised

---

## Phase C — ns-3 Export (planned)
Export the planned scenario to ns-3 C++ / Python script format.
Skeleton exists at `adapters/ns3_scenario_adapter.py`.

---

## Automated Tests
```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
Tests cover: propagation calculator, relation calculation service, schema v1/v2 round-trip.
