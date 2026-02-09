# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean-language nurse scheduling desktop application for an ER (응급실). Generates monthly shift schedules with constraint satisfaction using OR-Tools CP-SAT solver. Built with PyQt6 for the UI.

## Development Commands

```bash
# Install dependencies (uses uv package manager)
uv sync

# Run the application
uv run python main.py

# Build standalone exe (Windows) — uses PyInstaller
build.bat
```

Python 3.12+ required. Dependencies: PyQt6, ortools, openpyxl.

## Architecture

**Two-layer design: `engine/` (data + logic) and `ui/` (PyQt6 views)**

### engine/ — Backend logic, no UI dependencies
- **models.py** — Core dataclasses and constants. `Nurse` has role/grade/pregnancy/gender/4-day-week flags and a `fixed_weekly_off` day. `Request` normalizes exclusion codes (e.g. "D제외" → "D 제외") and has properties `is_hard`, `is_exclude`, `is_work_request`, `is_off_request`. `Rules` has daily staffing counts, night limits, consecutive work limits, weekly off, grade requirements, pregnancy/menstrual rules, and sleep-off conditions. `Schedule` wraps `schedule_data[nurse_id][day] = shift_code`. `DataManager` handles JSON persistence to `data/` with auto-backup to `~/Documents/NurseScheduler_backup/`.
- **solver.py** — `solve_schedule()` uses OR-Tools CP-SAT with 16 hard constraints and 4 soft objectives (request fulfillment, D/E/N fairness, night equity, weekend equity). Variables: `shifts[(nurse_idx, day_idx, shift_idx)]` as BoolVars. Shift indices: D=0, E=1, N=2, OFF=3. Solver runs with 4 workers and configurable timeout (default 30s).
- **validator.py** — `validate_change()` checks 7 constraint types for manual cell edits: shift eligibility, forbidden patterns (both directions), consecutive work/night limits, minimum staffing, and preceptor pairing.
- **evaluator.py** — `evaluate_schedule()` scores schedule fairness (0-100, grades A-F) based on shift deviation, night/weekend equity, bad patterns, and request fulfillment rate.
- **excel_io.py** — `export_schedule()` writes a two-sheet xlsx (schedule + stats). `import_nurses()` auto-detects "settings" vs "calendar grid" format. `import_requests()` reads calendar grid format.

### ui/ — PyQt6 widgets, one file per tab
- **main_window.py** — `MainWindow` with 4-tab `QTabWidget`. Owns `DataManager` and passes it to all tabs. Tab switching triggers data sync via `_on_tab_changed`.
- **setup_tab.py** — Tab 1. Nurse roster with editable table (name, skill level, D/E/N toggles, fixed shift, weekday-only, preceptor target, notes). Supports Excel import.
- **request_tab.py** — Tab 2. Calendar grid of `QComboBox` per nurse×day. Color-coded by request type.
- **rules_tab.py** — Tab 3. Scheduling constraints form: weekday/weekend min staffing (separate), forbidden patterns (N→D, N→E, E→D), consecutive limits, monthly off range, team composition rules.
- **result_tab.py** — Tab 4. Displays generated schedule in a color-coded grid. Supports inline editing with violation warnings. Shows per-shift aggregation rows, bad-pattern detection, and per-nurse statistics.
- **styles.py** — Color constants, request code lists, skill level labels, and the app-wide Qt stylesheet.

### Data flow
`SetupTab` → nurses/year/month → `RequestTab` → requests → `ResultTab` calls `solver.solve_schedule()` → `Schedule` displayed in grid. Manual edits go through `validator.validate_change()`. All tabs share a single `DataManager` instance for JSON I/O.

## Key Domain Concepts

- **Shift codes (7 work + 10 off)**: Work: `D`, `D9`, `D1`, `중1`, `중2`, `E`, `N`. Off: `주`, `OFF`, `POFF`, `법휴`, `수면`, `생휴`, `휴가`, `특휴`, `공가`, `경가`
- **Request codes**: Work preferences (`D`, `E`, `N`, etc.), off requests (`OFF`, `법휴`, `휴가`, etc.), exclusions (`D 제외`, `E 제외`, `N 제외`)
- **Roles (비고1)**: `책임만`, `외상`, `혼자 관찰불가`, `혼자 관찰`, `급성구역`, `준급성`, `소아` — with tiered staffing limits via `ROLE_TIERS`
- **Grades (비고2)**: `책임`, `서브차지`
- **Shift order**: D(1) → D9/D1/중1/중2(2) → E(3) → N(4). Reverse transitions forbidden via `ban_reverse_order`
- **`_building` flag**: Used across all tabs to suppress `cellChanged`/`currentTextChanged` signals during programmatic table updates

## Important Implementation Notes

- `engine/models.py` and `engine_ex/models.py` both exist with modifications in progress — the `models.py` in `engine/` has expanded shift/off codes (7 work types, 10 off types) vs the solver which still uses simplified D/E/N/OFF mapping
- The solver's `Rules` references attributes (`weekday_min_day`, `get_min_staff(shift, weekend)`, `ban_night_to_day`, `can_night`, `skill_level`, `preceptor_of`, `fixed_shift`, `weekday_only`) that differ from the `Rules` dataclass in `models.py` (`daily_D`, `daily_E`, `daily_N`, `max_N_per_month`, etc.) — the models and solver are being refactored and may be out of sync
- JSON persistence converts nurse IDs and days between `int` keys (in-memory) and `str` keys (JSON) in `save_schedule`/`load_schedule`
- `DataManager` resolves data directory relative to `engine/` parent when running from source, or relative to exe when packaged
