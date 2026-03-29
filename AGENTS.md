# Repository Guidelines

## Project Structure & Module Organization
`main.py` is the runtime entry point and `app.py` wires the application graph. Keep domain data in `models/`, orchestration and business rules in `services/`, persistence DTOs and JSON I/O in `storage/`, and ns-3 export adapters in `adapters/`. Put canvas-specific graphics code in `graphics/` and Qt widgets, panels, and tabs in `ui/`. Treat `README.md` as the current product scope and manual validation source for Phase A.

## Python environment
For all Python commands in this repository, use the project virtual environment interpreter:

- `.venv\Scripts\python.exe`

Validation commands for this repo:
- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- `.venv\Scripts\python.exe main.py`

Do not assume global Python or globally installed packages.

## Build, Test, and Development Commands
Create an isolated environment before development:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

`python main.py` launches the PySide6 desktop app locally. When adding tooling, prefer lightweight commands that work in PowerShell on Windows.

## Coding Style & Naming Conventions
Follow clean code and keep responsibilities separated by layer. Use 4-space indentation, type hints, and small focused classes/functions. Match existing naming: `PascalCase` for Qt widgets and services (`MainWindow`, `ScenarioService`), `snake_case` for modules and methods, and dataclass models ending in `Model` or `DTO`. Prefer explicit dependencies through constructors instead of global state. Before integrating new libraries or APIs, verify usage against official documentation.

## Testing Guidelines
There is no automated test suite yet. For changes, run the app and complete the manual checks in `README.md`: device add/remove, selection binding, drag/drop, keyboard nudging, zoom/pan, and JSON save/load. If you add tests, place them under `tests/` and use names like `test_scenario_service.py`.

## Commit & Pull Request Guidelines
Follow the existing Conventional Commit style: `feat(network-planner): ...`. Use scopes when they add clarity, and keep subjects imperative and specific. PRs should describe user-visible behavior, list manual validation steps, and attach screenshots or short recordings for UI changes. Link related issues and note any schema or file-format changes explicitly.

## Configuration & Data Notes
Persist scenario files as JSON through `storage/json_repository.py` and preserve the root `schema_version`. Do not commit `.venv/`, generated caches, or sample data containing local machine paths.

## Phase B Working Rules
When a task mentions "Phase B", "relations", "path loss", "RSSI", "SNR", "band", or "multi-link", read `docs/phase-b-handoff.md` before making any code changes.

Treat `docs/phase-b-handoff.md` as the active implementation handoff for Phase B. Keep its progress checklist and decision log updated when milestones are completed.

For complex Phase B work:
- inspect the current files first
- propose a short file-by-file plan before coding
- implement in small validated milestones
- avoid asking for next steps unless blocked by a real decision

Architecture constraints for Phase B:
- keep business logic in `services/`
- keep dataclass models in `models/`
- keep JSON schema and migration logic in `storage/`
- keep Qt widgets in `ui/` presentation-focused
- do not move calculation logic into `graphics/`
- do not add new third-party dependencies for Phase B
- prefer standard library `unittest` for pure calculation tests

Before finishing a milestone:
- run the relevant automated checks you added
- launch the app if possible
- report exactly what was validated
- report any remaining manual validation items