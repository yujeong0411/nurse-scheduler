"""NurseScheduler - 간호사 근무표 자동생성 프로그램"""
import sys
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
    main()
