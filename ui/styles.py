"""색상, 스타일 상수 — 응급실 간호사 근무표"""
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox
from PyQt6.QtCore import Qt

# ══════════════════════════════════════════
# 주 구분선 델리게이트
# ══════════════════════════════════════════

class WeekSeparatorDelegate(QStyledItemDelegate):
    """일요일 컬럼 구분선 + 요청 미반영 시 테두리 표시"""

    def __init__(self, sunday_cols: set[int], parent=None):
        super().__init__(parent)
        self.sunday_cols = sunday_cols

    def paint(self, painter, option, index):
        # 1. 기본 텍스트와 배경 그리기
        super().paint(painter, option, index)

        # 2. 일요일 구분선 그리기
        if index.column() in self.sunday_cols:
            painter.save()
            pen = QPen(QColor(80, 80, 80))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(
                option.rect.left(), option.rect.top(),
                option.rect.left(), option.rect.bottom(),
            )
            painter.restore()

        # 3. 요청 미반영 테두리 그리기
        # UserRole에 True가 설정되어 있다면 빨간 테두리 표시
        if index.data(Qt.ItemDataRole.UserRole):
            painter.save()
            # 테두리 색상 및 두께 설정 (빨간색, 2px)
            pen = QPen(QColor(255, 0, 0)) 
            pen.setWidth(2)
            # 테두리가 셀 안쪽으로 그려지도록 설정
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            painter.setPen(pen)
            
            # 셀 영역보다 1px 안쪽에 사각형 그리기
            rect = option.rect.adjusted(1, 1, -1, -1)
            painter.drawRect(rect)
            painter.restore()


class NoWheelComboBox(QComboBox):
    """마우스 휠로 값이 변하는 것을 방지하는 커스텀 콤보박스"""
    def wheelEvent(self, event):
        event.ignore()

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
    "OFF": QColor(252, 251, 146),
    "주": QColor(252, 251, 146),
    "법휴": QColor(252, 251, 146),
    "생휴": QColor(252, 251, 146),
    "수면": QColor(252, 251, 146),
    "POFF": QColor(252, 251, 146),
    "휴가": QColor(252, 251, 146),
    "특휴": QColor(252, 251, 146),
    "공가": QColor(252, 251, 146),
    "경가": QColor(252, 251, 146),
    "보수": QColor(252, 251, 146)
}

SHIFT_TEXT_COLORS = {
    # "D": QColor(7, 117, 250),
    # "D9": QColor(46, 117, 182),   # 중간 계열
    # "D1": QColor(46, 117, 182),   # 중간 계열
    # "중1": QColor(191, 143, 0),   # 중간 계열
    # "중2": QColor(7, 163, 54),
    # "E": QColor(161, 8, 158),
    "N": QColor(214, 21, 6),
    # "OFF": QColor(214, 21, 6),
    # "주": QColor(214, 21, 6),
    # "법휴": QColor(214, 21, 6),
    # "생휴": QColor(204, 0, 0),
    # "수면": QColor(214, 21, 6),
    # "POFF": QColor(214, 21, 6),
    # "휴가": QColor(148, 84, 13), 
    # "특휴": QColor(214, 21, 6),
    # "공가": QColor(156, 87, 0),
    # "경가": QColor(156, 87, 0),
    # "보수": QColor(156, 87, 0)
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
    "", "D", "E", "N", "중2",
    "OFF", "주", "법휴", "생휴", "수면", "휴가", "특휴", "공가", "경가",
    "D 제외", "E 제외", "N 제외",
]

# 결과 탭 수동 수정용
SHIFT_TYPES = [
    "D", "E", "N", "중2",
    "OFF", "주", "법휴", "생휴", "수면", "POFF", "휴가", "특휴", "공가", "경가",
]

# 간호사 속성 옵션
ROLE_OPTIONS = [
    "", "책임만", "외상", "혼자관찰", "혼자 관찰", "혼자관찰불가",
    "격리구역", "급성구역", "준급성", "중2"
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
    background-color: #f3f6fa;
}

/* =========================
   탭 영역
========================= */
QTabWidget::pane {
    border: none;
    background: white;
    border-radius: 10px;
}

QTabBar::tab {
    background: transparent;
    padding: 10px 24px;
    margin-right: 4px;
    border-radius: 8px;
    font-size: 11pt;
    font-family: '맑은 고딕';
    color: #555555;
}

QTabBar::tab:selected {
    background: white;
    font-weight: 600;
    color: #013976;
    border: 1px solid #e3e8ef;
}

QTabBar::tab:hover {
    background: #edf2f8;
}

/* =========================
   버튼
========================= */
QPushButton {
    background-color: #013976;
    color: white;
    border: none;
    padding: 8px 18px;
    border-radius: 8px;
    font-size: 10pt;
    font-family: '맑은 고딕';
}

QPushButton:hover {
    background-color: #0a4ea3;
}

QPushButton:pressed {
    background-color: #012a5c;
}

QPushButton#secondaryBtn {
    background-color: #e8edf3;
    color: #013976;
}

QPushButton#secondaryBtn:hover {
    background-color: #d8e2f0;
}

/* =========================
   테이블
========================= */
QTableWidget {
    background-color: white;
    border: 1px solid #e3e8ef;
    border-radius: 10px;
    gridline-color: #eef2f6;
    font-size: 10pt;
    font-family: '맑은 고딕';
}

QTableWidget::item {
    padding: 2px;
}

/* 헤더 */
QHeaderView::section {
    background-color: #013976;
    color: white;
    padding: 8px;
    border: none;
    font-weight: 600;
    font-size: 10pt;
    font-family: '맑은 고딕';
}

/* =========================
   콤보박스
========================= */
QComboBox {
    border: 1px solid #d9e1ec;
    border-radius: 4px;
    padding: 2px 4px;
    background: white;
    font-size: 10pt;
    font-family: '맑은 고딕';
}

QComboBox:hover {
    border: 1px solid #013976;
}

QComboBox QAbstractItemView {
    background-color: white;
    border: 1px solid #d9e1ec;
    selection-background-color: #e8f0fb;
    padding: 4px;
}

/* =========================
   GroupBox
========================= */
QGroupBox {
    font-family: '맑은 고딕';
    font-size: 10pt;
    font-weight: 600;
    border: 1px solid #e3e8ef;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 18px;
    background: white;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 6px;
    color: #013976;
}

/* =========================
   SpinBox
========================= */
QSpinBox {
    border: 1px solid #d9e1ec;
    border-radius: 6px;
    padding: 4px 6px;
    background: white;
}

/* =========================
   체크박스
========================= */
QCheckBox {
    font-family: '맑은 고딕';
    font-size: 10pt;
    spacing: 8px;
}
"""
