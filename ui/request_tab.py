"""Tab 2: 요청사항 달력 — 응급실"""
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from engine.models import Nurse, Request, DataManager
from ui.styles import (
    REQUEST_CODES, SHIFT_COLORS,
    FONT_FAMILY, NoWheelComboBox, WeekSeparatorDelegate
)

class RequestTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.dm = data_manager
        self.nurses: list[Nurse] = []
        self.start_date = date(2026, 3, 1)
        self.requests: list[Request] = []
        self._building = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 상단 정보
        top = QHBoxLayout()
        self.title_label = QLabel("2026년 3월 개인 요청사항")
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
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

    def refresh(self, nurses: list[Nurse], start_date: date):
        self.nurses = nurses
        self.start_date = start_date
        end_date = start_date + timedelta(days=27)
        self.title_label.setText(
            f"{start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')} 개인 요청사항"
        )
        self.requests = self.dm.load_requests(start_date)
        self._rebuild_table()

    def _rebuild_table(self):
        self._building = True
        num_days = 28
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]

        self.table.clear()
        self.table.setRowCount(len(self.nurses))
        self.table.setColumnCount(num_days + 1)

        # 헤더: 실제 날짜 표시
        headers = ["이름"]
        for d in range(1, num_days + 1):
            dt = self.start_date + timedelta(days=d - 1)
            wd = dt.weekday()
            headers.append(f"{dt.month}/{dt.day}\n({weekday_names[wd]})")
        self.table.setHorizontalHeaderLabels(headers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 80)
        for d in range(1, num_days + 1):
            header.setSectionResizeMode(d, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(d, 78)

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
                wd = (self.start_date + timedelta(days=d - 1)).weekday()

                combo = NoWheelComboBox()
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

        # ── 일요일 컬럼 구분선 적용 ──
        DAY_START = 1  # 요청탭은 이름(0) 다음이 바로 날짜

        sunday_cols = set()
        for d in range(1, num_days + 1):
            if (self.start_date + timedelta(days=d - 1)).weekday() == 6:  # 일요일
                sunday_cols.add(DAY_START + d - 1)

        self._week_delegate = WeekSeparatorDelegate(sunday_cols, self.table)
        self.table.setItemDelegate(self._week_delegate)

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
            wd = (self.start_date + timedelta(days=day - 1)).weekday()
            self._apply_combo_style(combo, code, wd)

        # 요청 리스트 업데이트
        self.requests = [
            r for r in self.requests
            if not (r.nurse_id == nurse.id and r.day == day)
        ]
        if code:
            self.requests.append(Request(nurse_id=nurse.id, day=day, code=code))

    def _save_requests(self):
        self.dm.save_requests(self.requests, self.start_date)
        QMessageBox.information(self, "저장", "요청사항이 저장되었습니다.")

    def get_requests(self) -> list[Request]:
        return self.requests
