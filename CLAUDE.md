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

Python 3.12+ required. Dependencies: PyQt6, ortools, openpyxl. No test suite exists.

## Architecture

**Two-layer design: `engine/` (data + logic) and `ui/` (PyQt6 views)**

### engine/ — Backend logic, no UI dependencies
- **models.py** — Core dataclasses (`Nurse`, `Request`, `Rules`, `Schedule`) and constants (`WORK_SHIFTS`, `OFF_TYPES`, `SHIFT_ORDER`, `ROLE_TIERS`). `Request` normalizes exclusion codes (e.g. "D제외" → "D 제외") and has properties `is_hard`, `is_exclude`, `is_work_request`, `is_off_request`. `DataManager` handles JSON persistence to `data/` with auto-backup to `~/Documents/NurseScheduler_backup/`. Sleep-off helpers: `get_sleep_partner_month`, `get_sleep_pair`, `is_pair_first_month`.
- **solver.py** — `solve_schedule()` uses OR-Tools CP-SAT with 23 hard constraints (H1-H17 as CP-SAT constraints, H18-H23 as post-processing) and 5 soft objectives. Variables: `shifts[(nurse_idx, day_idx, shift_idx)]` as BoolVars. Shift indices: D=0, E=1, N=2, OFF=3. Solver runs with 4 workers and configurable timeout (default 60s). Post-processing converts generic OFF → labeled off types (주/법휴/생휴/수면/POFF). See docstring at top of file for full constraint list.
- **validator.py** — `validate_change()` checks 16 constraint types for manual cell edits: reverse order (both directions), consecutive work/night limits, NN→2 off, monthly N limit, weekly off, daily staffing minimums, grade/role tier requirements, legal holidays, 4-day week, pregnancy limits, vacation balance.
- **evaluator.py** — `evaluate_schedule()` scores schedule fairness (0-100, grades A-F) based on shift deviation, night/weekend equity, bad patterns, and request fulfillment rate.
- **excel_io.py** — `export_schedule()` writes a two-sheet xlsx (schedule + stats). `import_nurse_rules()` reads nurse settings from 근무표_규칙.xlsx. `import_requests()` reads calendar grid format. `import_nurses_from_request()` extracts nurse names from request files.

### ui/ — PyQt6 widgets, one file per tab
- **main_window.py** — `MainWindow` with 4-tab `QTabWidget`. Owns `DataManager` and passes it to all tabs. Tab switching triggers data sync via `_on_tab_changed`.
- **setup_tab.py** — Tab 1. Nurse roster table (name, role, grade, pregnant, male, 4-day-week, fixed weekly off, vacation balance, prev month N count, pending sleep, notes). Supports Excel import.
- **request_tab.py** — Tab 2. Calendar grid of `QComboBox` per nurse×day. Color-coded by request type.
- **rules_tab.py** — Tab 3. Scheduling constraints form: staffing minimums, forbidden patterns, consecutive limits, grade requirements, pregnancy/menstrual rules, sleep conditions, public holidays.
- **result_tab.py** — Tab 4. Displays generated schedule in a color-coded grid. Supports inline editing with violation warnings. Shows per-shift aggregation rows, bad-pattern detection, and per-nurse statistics with A-F grading.
- **styles.py** — `SHIFT_COLORS` dict, `REQUEST_CODES` list, `SKILL_LEVELS` labels, and the app-wide Qt stylesheet.

### Data flow
`SetupTab` → nurses/year/month → `RequestTab` → requests → `ResultTab` calls `solver.solve_schedule()` → `Schedule` displayed in grid. Manual edits go through `validator.validate_change()`. All tabs share a single `DataManager` instance for JSON I/O.

## Key Domain Concepts

- **Shift codes**: Currently active work shifts: `D`, `E`, `N` (mid-shifts `D9`, `D1`, `중1`, `중2` are defined but commented out for future expansion). Off types (11): `주`, `OFF`, `POFF`, `법휴`, `수면`, `생휴`, `휴가`, `특휴`, `공가`, `경가`
- **Request codes**: Work preferences (`D`, `E`, `N`), off requests (`OFF`, `법휴`, `휴가`, etc.), exclusions (`D 제외`, `E 제외`, `N 제외`)
- **Roles (비고1)**: `책임만`, `외상`, `혼자 관찰불가`, `혼자 관찰`, `급성구역`, `준급성`, `격리구역(소아)` — with tiered cumulative staffing limits via `ROLE_TIERS`
- **Grades (비고2)**: `책임`, `서브차지`
- **Shift order**: D(1) → E(2) → N(3). Reverse transitions forbidden via `ban_reverse_order`. When mid-shifts are added: D(1) → M(2) → E(3) → N(4)
- **Sleep off**: Calculated in fixed 2-month pairs `[(1,2), (3,4), (5,6), (7,8), (9,10), (11,12)]`. Monthly threshold: N ≥ 7. Bimonthly (even months): prev_N + current_N ≥ 11. Odd months carry `pending_sleep` to next month
- **`_building` flag**: Used across all UI tabs to suppress `cellChanged`/`currentTextChanged` signals during programmatic table updates

## Important Implementation Notes

- The solver uses simplified D/E/N/OFF (NUM_TYPES=4). Mid-shift expansion to 7 work types is planned but commented out throughout `models.py` and `solver.py`
- Solver post-processing (after CP-SAT solve) labels generic OFF → 주/법휴/생휴/수면/POFF based on rules, public holidays, gender, pregnancy, and night-shift counts
- JSON persistence converts nurse IDs and days between `int` keys (in-memory) and `str` keys (JSON) in `save_schedule`/`load_schedule`
- `DataManager` resolves data directory relative to `engine/` parent when running from source, or relative to exe when packaged
