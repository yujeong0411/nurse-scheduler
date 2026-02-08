# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean-language nurse scheduling desktop application. Generates monthly 3-shift (Day/Evening/Night) schedules with constraint satisfaction. Built with PyQt6 for the UI and OR-Tools for optimization (solver is currently a placeholder using random assignment).

## Development Commands

```bash
# Install dependencies (uses uv package manager)
uv sync

# Run the application
uv run python main.py

# Build standalone exe (Windows)
build.bat
```

Python 3.12 required. Dependencies: PyQt6, ortools, openpyxl.

## Architecture

**Two-layer design: `engine/` (data + logic) and `ui/` (PyQt6 views)**

### engine/ — Backend logic, no UI dependencies
- **models.py** — Core dataclasses (`Nurse`, `Request`, `Rules`, `Schedule`) and `DataManager` for JSON persistence. `DataManager` saves to `data/` and auto-backs up to `~/Documents/NurseScheduler_backup/`. JSON keys are converted str↔int for nurse IDs and days.
- **solver.py** — `solve_schedule()` returns a populated `Schedule`. Currently a simple random-assignment placeholder; intended to be replaced with OR-Tools CP-SAT solver.
- **validator.py** — `validate_change()` checks 7 constraint types when a user manually edits a cell in the result table. Returns a list of violation strings (empty = valid).
- **evaluator.py** — Stub. `evaluate_schedule()` is meant to score schedule fairness.
- **excel_io.py** — Stub. `export_schedule()` raises `NotImplementedError`.

### ui/ — PyQt6 widgets, one file per tab
- **main_window.py** — `MainWindow` with 4-tab `QTabWidget`. Owns `DataManager` and passes it to all tabs. Tab switching triggers data sync: switching to request tab refreshes nurse list; switching to result tab passes nurses/requests/rules.
- **setup_tab.py** — Tab 1. Nurse roster management with editable table. Year/month selector. Emits `nurses_changed` signal.
- **request_tab.py** — Tab 2. Calendar grid of `QComboBox` per nurse×day. Codes: `OFF`, `연차`(annual leave), `D/E/N`(preferred), `D!/E!/N!`(mandatory).
- **rules_tab.py** — Tab 3. Scheduling constraints form (min staffing, forbidden shift patterns, consecutive limits, team composition rules).
- **result_tab.py** — Tab 4. Displays generated schedule in a color-coded grid. Supports inline editing with violation warnings via `validator.py`. Shows per-shift aggregation rows and bad-pattern detection.
- **styles.py** — Color constants (`SHIFT_COLORS`, `SHIFT_TEXT_COLORS`), request codes list, skill level labels, and the app-wide Qt stylesheet.

### Data flow
`SetupTab` → nurses/year/month → `RequestTab` → requests → `ResultTab` calls `solver.solve_schedule()` → `Schedule` displayed in grid. Manual edits in the grid go through `validator.validate_change()` before applying.

## Key Domain Concepts

- **Shift types**: `D` (Day), `E` (Evening), `N` (Night), `OFF`
- **Request codes**: `OFF`/`연차` (time off), `D/E/N` (soft preference), `D!/E!/N!` (hard constraint)
- **Skill levels**: 1=신규(new), 2=일반(regular), 3=주임(charge), 4=책임(senior)
- **Forbidden patterns**: N→D, N→E, E→D (configurable in Rules)
- **Preceptor pairing**: A senior nurse (`preceptor_of` field) is locked to the same shift as their assigned new nurse
- **`_building` flag**: Used across all tabs to suppress `cellChanged`/`currentTextChanged` signals during programmatic table updates

## Incomplete Features (Stubs/TODOs)

- `solver.py`: Replace random assignment with OR-Tools CP-SAT solver
- `evaluator.py`: Implement fairness scoring
- `excel_io.py`: Implement Excel export via openpyxl
