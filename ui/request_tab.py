"""Tab 2: 요청사항 달력 — 응급실"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QComboBox, QPushButton, QHeaderView,
    QMessageBox, QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QBrush
from engine.models import Nurse, Request, DataManager
from ui.styles import (
    REQUEST_CODES, SHIFT_COLORS, SHIFT_TEXT_COLORS,
    WEEKEND_BG, FONT_FAMILY,
)
import calendar


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
        self.title_label = QLabel("2026년 2월 개인 요청사항")
        self.title_label.setFont(QFont(FONT_FAMILY, 13, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #013976;")
        top.addWidget(self.title_label)
        top.addStretch()

        save_btn = QPushButton("요청사항 저장")
        save_btn.clicked.connect(self._save_requests)
        top.addWidget(save_btn)

        layout.addLayout(top)

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

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 80)
        for d in range(1, num_days + 1):
            header.setSectionResizeMode(d, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(d, 56)

        # 요청 맵
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

                combo = QComboBox()
                combo.addItems(REQUEST_CODES)
                combo.setStyleSheet("font-size: 9pt; border: none;")

                if code in REQUEST_CODES:
                    combo.setCurrentText(code)

                # 배경색
                self._apply_combo_style(combo, code, wd)

                combo.currentTextChanged.connect(
                    lambda text, r=row, c=d: self._on_request_changed(r, c, text)
                )
                self.table.setCellWidget(row, d, combo)

            self.table.setRowHeight(row, 30)

        self._building = False

    def _apply_combo_style(self, combo, code, weekday):
        """콤보박스에 코드에 맞는 색상 적용"""
        base = "font-size: 9pt; border: none; "
        if code and code in SHIFT_COLORS:
            c = SHIFT_COLORS[code]
            combo.setStyleSheet(
                base + f"background-color: rgb({c.red()},{c.green()},{c.blue()});"
            )
        elif weekday >= 5:
            combo.setStyleSheet(base + "background-color: #f2f2f2;")
        else:
            combo.setStyleSheet(base)

    def _on_request_changed(self, row, day, code):
        if self._building or row >= len(self.nurses):
            return
        nurse = self.nurses[row]

        # 스타일 업데이트
        combo = self.table.cellWidget(row, day)
        if combo:
            wd = calendar.weekday(self.year, self.month, day)
            self._apply_combo_style(combo, code, wd)

        # 요청 리스트 업데이트
        self.requests = [
            r for r in self.requests
            if not (r.nurse_id == nurse.id and r.day == day)
        ]
        if code:
            self.requests.append(Request(nurse_id=nurse.id, day=day, code=code))

    def _save_requests(self):
        self.dm.save_requests(self.requests, self.year, self.month)
        QMessageBox.information(self, "저장", "요청사항이 저장되었습니다.")

    def get_requests(self) -> list[Request]:
        return self.requests
