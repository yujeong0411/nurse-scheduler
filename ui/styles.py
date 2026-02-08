"""색상, 스타일 상수"""
from PyQt6.QtGui import QColor

# 근무 타입별 색상
SHIFT_COLORS = {
    "D":   QColor(218, 238, 243),   # 연파랑
    "E":   QColor(253, 233, 217),   # 연주황
    "N":   QColor(228, 223, 236),   # 연보라
    "OFF": QColor(216, 228, 188),   # 연초록
    "연차": QColor(255, 153, 153),  # 연빨강
}

SHIFT_TEXT_COLORS = {
    "D":   QColor(46, 117, 182),    # 파랑
    "E":   QColor(197, 90, 17),     # 주황
    "N":   QColor(112, 48, 160),    # 보라
    "OFF": QColor(84, 130, 53),     # 초록
    "연차": QColor(204, 0, 0),      # 빨강
}

WEEKEND_BG = QColor(242, 242, 242)         # 주말 배경
VIOLATION_BG = QColor(255, 200, 200)       # 위반 배경
VIOLATION_BORDER = QColor(255, 0, 0)       # 위반 테두리
HEADER_BG = QColor(0, 57, 118)            # 헤더 배경 (진파랑)
HEADER_TEXT = QColor(255, 255, 255)        # 헤더 텍스트 (흰색)
SHORTAGE_BG = QColor(255, 220, 220)        # 인원부족 배경

# 근무 코드 목록
SHIFT_TYPES = ["", "D", "E", "N", "OFF"]
REQUEST_CODES = ["", "OFF", "연차", "D", "E", "N", "D!", "E!", "N!"]
SKILL_LEVELS = {1: "신규", 2: "일반", 3: "주임", 4: "책임"}
FIXED_SHIFT_OPTIONS = ["없음", "D", "E", "N"]

# 폰트
FONT_FAMILY = "맑은 고딕"
FONT_SIZE = 10
FONT_SIZE_SMALL = 9
FONT_SIZE_HEADER = 11

# 앱 스타일시트  #003976
APP_STYLE = """
QMainWindow {
    background-color: #f5f5f5;
}
QTabWidget::pane {
    border: 1px solid #cccccc;
    background: white;
}
QTabBar::tab {
    background: #e0e0e0;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-size: 11pt;
    font-family: '맑은 고딕';
}
QTabBar::tab:selected {
    background: white;
    font-weight: bold;
    color: #003976;
}
QTabBar::tab:hover {
    background: #d0d8e8;
}
QPushButton {
    background-color: #003976;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 10pt;
    font-family: '맑은 고딕';
}
QPushButton:hover {
    background-color: #3a6bc5;
}
QPushButton:pressed {
    background-color: #1d3a6a;
}
QPushButton#dangerBtn {
    background-color: #c0392b;
}
QPushButton#dangerBtn:hover {
    background-color: #e74c3c;
}
QPushButton#secondaryBtn {
    background-color: #7f8c8d;
}
QPushButton#secondaryBtn:hover {
    background-color: #95a5a6;
}
QTableWidget {
    gridline-color: #d0d0d0;
    font-size: 10pt;
    font-family: '맑은 고딕';
}
QTableWidget::item {
    padding: 4px;
}
QTableWidget::item:hover {
    background-color: #E8F0FE;
}
QTableWidget::item:selected {
    background-color: #D0E0F0;
    color: black;
}
QHeaderView::section {
    background-color: #003976;
    color: white;
    padding: 6px;
    border: 1px solid #1d3a6a;
    font-weight: bold;
    font-size: 10pt;
    font-family: '맑은 고딕';
}
QLabel {
    font-family: '맑은 고딕';
}
QSpinBox, QComboBox {
    font-family: '맑은 고딕';
    font-size: 11pt;
    padding: 4px;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
}
QGroupBox {
    font-family: '맑은 고딕';
    font-size: 10pt;
    font-weight: bold;
    border: 1px solid #cccccc;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 16px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #003976;
}
QCheckBox {
    font-family: '맑은 고딕';
    font-size: 10pt;
    spacing: 8px;
}
"""
