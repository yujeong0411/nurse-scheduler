"""NurseScheduler - 간호사 근무표 자동생성 프로그램"""
import sys
import os
import traceback

# ── exe 서브프로세스 솔버 모드 ──
# PyQt6 로드 전에 분기하여 충돌 방지
if getattr(sys, 'frozen', False) and len(sys.argv) > 1 and sys.argv[1] == '--solve':
    try:
        import pickle
        input_path = sys.argv[2]
        output_path = sys.argv[3]

        with open(input_path, 'rb') as f:
            data = pickle.load(f)

        from engine.solver import solve_schedule
        schedule = solve_schedule(
            data['nurses'], data['requests'], data['rules'], data['start_date']
        )

        result = schedule.schedule_data if schedule and schedule.schedule_data else {}
        with open(output_path, 'wb') as f:
            pickle.dump(result, f)
    except Exception:
        # 에러 시 빈 결과 저장
        import pickle
        try:
            with open(sys.argv[3], 'wb') as f:
                pickle.dump({}, f)
        except Exception:
            pass
        # 로그 파일에 에러 기록
        log_path = os.path.join(os.path.dirname(sys.executable), "solver_crash.log")
        with open(log_path, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
    sys.exit(0)

# ── 일반 GUI 모드 ──
# exe 실행 시 에러를 로그 파일로 저장
if getattr(sys, 'frozen', False):
    _log_path = os.path.join(os.path.dirname(sys.executable), "crash.log")
    sys.stderr = open(_log_path, "w", encoding="utf-8")

import ortools.sat.python.cp_model as _  # noqa: F401  # PyQt6보다 먼저 로드 (segfault 방지)
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # 기본 폰트
    font = QFont("맑은 고딕", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
