"""색상, 스타일 상수 — 응급실 간호사 근무표"""
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QStyledItemDelegate

# ══════════════════════════════════════════
# 주 구분선 델리게이트
# ══════════════════════════════════════════

class WeekSeparatorDelegate(QStyledItemDelegate):
    """일요일 컬럼 왼쪽에 굵은 구분선"""

    def __init__(self, sunday_cols: set[int], parent=None):
        super().__init__(parent)
        self.sunday_cols = sunday_cols

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.column() in self.monday_cols:
            painter.save()
            pen = QPen(QColor(80, 80, 80))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(
                option.rect.left(), option.rect.top(),
                option.rect.left(), option.rect.bottom(),
            )
            painter.restore()

# ══════════════════════════════════════════
# 근무/휴무 배경 색상 (17종 + OFF)
# ══════════════════════════════════════════
SHIFT_COLORS = {
    # 근무 (3종, 중간근무 추가 시 7종)
    # "D":   QColor(234, 209, 220),
    # "D9":  QColor(180, 225, 232),   # 중간 계열
    # "D1":  QColor(180, 225, 232),   # 중간 계열
    # "중1":  QColor(253, 235, 208),  # 중간 계열
    # "중2":  QColor(253, 235, 208),  # 중간 계열
    # "E":   QColor(253, 233, 217),
    # "N":   QColor(228, 223, 236),
    # 휴무 (10종)
    "OFF":  QColor(252, 251, 146),
    "주":   QColor(252, 251, 146),
    "법휴": QColor(252, 251, 146),
    "생휴":   QColor(252, 251, 146),
    "수면": QColor(252, 251, 146),
    "POFF": QColor(252, 251, 146),
    "휴가":   QColor(252, 251, 146),
    "특휴": QColor(252, 251, 146),
    "공가":   QColor(252, 251, 146),
    "경가":   QColor(252, 251, 146),
}

SHIFT_TEXT_COLORS = {
    "D":   QColor(7, 117, 250),
    # "D9":  QColor(46, 117, 182),   # 중간 계열
    # "D1":  QColor(46, 117, 182),   # 중간 계열
    # "중1":  QColor(191, 143, 0),   # 중간 계열
    # "중2":  QColor(191, 143, 0),   # 중간 계열
    "E":   QColor(209, 120, 4),
    "N":   QColor(214, 21, 6),
    # "OFF": QColor(214, 21, 6),
    # "주":   QColor(214, 21, 6),
    # "법휴": QColor(214, 21, 6),
    # "생휴":   QColor(204, 0, 0),
    # "수면": QColor(214, 21, 6),
    # "POFF": QColor(214, 21, 6),
    # "휴가":   QColor(148, 84, 13), 
    # "특휴": QColor(214, 21, 6),
    # "공가":   QColor(156, 87, 0),
    # "경가":   QColor(156, 87, 0),
}

WEEKEND_BG = QColor(242, 242, 242)
VIOLATION_BG = QColor(255, 200, 200)
HEADER_BG = QColor(1, 57, 118)
HEADER_TEXT = QColor(255, 255, 255)
SHORTAGE_BG = QColor(255, 220, 220)

# ══════════════════════════════════════════
# 드롭다운 옵션
# ══════════════════════════════════════════

# 요청사항 탭 코드 (빈칸 = 자동배정)
REQUEST_CODES = [
    "", "D", "E", "N",
    # "D9", "D1", "중1", "중2",  # 중간근무 추가 시
    "OFF", "주", "법휴", "생휴", "수면", "휴가", "특휴", "공가", "경가",
    "D 제외", "E 제외", "N 제외",
    # "M 제외",  # 중간근무 추가 시
]

# 결과 탭 수동 수정용
SHIFT_TYPES = [
    "D", "E", "N",
    # "D9", "D1", "중1", "중2",  # 중간근무 추가 시
    "OFF", "주", "법휴", "생휴", "수면", "POFF", "휴가", "특휴", "공가", "경가",
]

# 간호사 속성 옵션
ROLE_OPTIONS = [
    "", "책임만", "외상", "혼자관찰", "혼자 관찰", "혼자관찰불가",
    "격리구역", "급성구역", "준급성"
]
GRADE_OPTIONS = ["", "책임", "서브차지"]
WEEKDAY_OPTIONS = ["없음", "월", "화", "수", "목", "금", "토", "일"]

# 폰트
FONT_FAMILY = "맑은 고딕"

# ══════════════════════════════════════════
# 앱 스타일시트
# ══════════════════════════════════════════
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
    color: #013976;
}
QTabBar::tab:hover {
    background: #d0d8e8;
}
QPushButton {
    background-color: #013976;
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
QHeaderView::section {
    background-color: #013976;
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
QComboBox {
    font-family: '맑은 고딕';
    font-size: 10pt;
    padding: 0.5px 0.5px 0.5px 4px; /* 상우하좌: 여백을 줄여 텍스트 공간 확보 */
    margin: 0px;
}
QComboBox QAbstractItemView {
    min-width: 62px; /* 리스트의 최소 너비를 확보하여 텍스트가 잘리지 않게 함 */
    background-color: white;
    selection-background-color: #d0d8e8;
    padding: 2px;
}
QSpinBox {
    font-family: '맑은 고딕';
    font-size: 10pt;
    padding: 4px 6px;
    min-height: 28px;
}
QSpinBox::up-button, QSpinBox::down-button {
    min-width: 20px;
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
    color: #013976;
}
QCheckBox {
    font-family: '맑은 고딕';
    font-size: 10pt;
    spacing: 8px;
}
"""
