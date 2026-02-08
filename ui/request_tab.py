"""Tab 2: 요청사항 달력"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QComboBox, QPushButton, QHeaderView,
    QMessageBox, QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QBrush
from engine.models import Nurse, Request, DataManager
from ui.styles import (
    REQUEST_CODES, WEEKEND_BG, FONT_FAMILY, SHIFT_COLORS, SHIFT_TEXT_COLORS,
)
import calendar


REQUEST_COLORS = {
    "OFF": QColor(180, 198, 231),
    "연차": QColor(255, 153, 153),
    "D":   QColor(189, 215, 238),
    "E":   QColor(255, 214, 153),
    "N":   QColor(226, 191, 255),
    "D!":  QColor(146, 195, 220),
    "E!":  QColor(255, 185, 100),
    "N!":  QColor(200, 160, 230),
}


class RequestTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.dm = data_manager
        self.nurses: list[Nurse] = []
        self.year = 2026
        self.month = 3
        self.requests: list[Request] = []
        self._building = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 상단 정보
        top = QHBoxLayout()
        self.title_label = QLabel("2026년 3월 개인 요청사항")
        self.title_label.setFont(QFont(FONT_FAMILY, 13, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #2F5496;")
        top.addWidget(self.title_label)
        top.addStretch()

        save_btn = QPushButton("요청사항 저장")
        save_btn.clicked.connect(self._save_requests)
        top.addWidget(save_btn)

        layout.addLayout(top)

        # 범례
        legend = QGroupBox("입력 코드")
        legend_layout = QHBoxLayout(legend)
        codes = [
            ("(빈칸)", "자동배정", "#ffffff"),
            ("OFF", "희망휴무", "#B4C6E7"),
            ("연차", "확정휴무", "#FF9999"),
            ("D/E/N", "희망근무", "#BDD7EE"),
            ("D!/E!/N!", "고정(필수)", "#92C3DC"),
        ]
        for code, desc, color in codes:
            lbl = QLabel(f"  {code} = {desc}  ")
            lbl.setStyleSheet(f"background: {color}; padding: 4px 8px; border-radius: 3px; font-size: 9pt;")
            legend_layout.addWidget(lbl)
        legend_layout.addStretch()
        layout.addWidget(legend)

        # 달력 테이블
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

    def refresh(self, nurses: list[Nurse], year: int, month: int):
        self.nurses = nurses
        self.year = year
        self.month = month
        self.title_label.setText(f"{year}년 {month}월 개인 요청사항")

        # 기존 요청 불러오기
        self.requests = self.dm.load_requests(year, month)
        self._rebuild_table()

    def _rebuild_table(self):
        self._building = True
        num_days = calendar.monthrange(self.year, self.month)[1]
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]

        self.table.clear()
        self.table.setRowCount(len(self.nurses))
        self.table.setColumnCount(num_days + 1)

        # 헤더
        headers = ["이름"]
        for d in range(1, num_days + 1):
            wd = calendar.weekday(self.year, self.month, d)
            headers.append(f"{d}\n({weekday_names[wd]})")
        self.table.setHorizontalHeaderLabels(headers)

        # 헤더 스타일
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 80)
        for d in range(1, num_days + 1):
            header.setSectionResizeMode(d, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(d, 52)

        self.table.setRowHeight(0, 32)

        # 요청 맵 구성
        req_map = {}
        for r in self.requests:
            req_map[(r.nurse_id, r.day)] = r.code

        # 데이터 채우기
        for row, nurse in enumerate(self.nurses):
            # 이름
            name_item = QTableWidgetItem(nurse.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, name_item)

            for d in range(1, num_days + 1):
                code = req_map.get((nurse.id, d), "")
                wd = calendar.weekday(self.year, self.month, d)

                # 콤보박스
                combo = QComboBox()
                combo.addItems(REQUEST_CODES)
                combo.setStyleSheet("font-size: 9pt; border: none;")

                if code in REQUEST_CODES:
                    combo.setCurrentText(code)

                # 배경색
                if code and code in REQUEST_COLORS:
                    color = REQUEST_COLORS[code]
                    combo.setStyleSheet(
                        f"font-size: 9pt; border: none; "
                        f"background-color: rgb({color.red()},{color.green()},{color.blue()});"
                    )
                elif wd >= 5:
                    combo.setStyleSheet(
                        f"font-size: 9pt; border: none; background-color: #f2f2f2;"
                    )

                combo.currentTextChanged.connect(
                    lambda text, r=row, c=d: self._on_request_changed(r, c, text)
                )
                self.table.setCellWidget(row, d, combo)

            self.table.setRowHeight(row, 30)

        self._building = False

    def _on_request_changed(self, row, day, code):
        if self._building or row >= len(self.nurses):
            return
        nurse = self.nurses[row]

        # 콤보 스타일 업데이트
        combo = self.table.cellWidget(row, day)
        if combo:
            if code and code in REQUEST_COLORS:
                color = REQUEST_COLORS[code]
                combo.setStyleSheet(
                    f"font-size: 9pt; border: none; "
                    f"background-color: rgb({color.red()},{color.green()},{color.blue()});"
                )
            else:
                wd = calendar.weekday(self.year, self.month, day)
                if wd >= 5:
                    combo.setStyleSheet("font-size: 9pt; border: none; background-color: #f2f2f2;")
                else:
                    combo.setStyleSheet("font-size: 9pt; border: none;")

        # 요청 리스트 업데이트
        self.requests = [r for r in self.requests if not (r.nurse_id == nurse.id and r.day == day)]
        if code:
            self.requests.append(Request(nurse_id=nurse.id, day=day, code=code))

    def _save_requests(self):
        self.dm.save_requests(self.requests, self.year, self.month)
        QMessageBox.information(self, "저장", "요청사항이 저장되었습니다.")

    def get_requests(self) -> list[Request]:
        return self.requests
