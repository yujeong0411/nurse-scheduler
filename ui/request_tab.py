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

        # 테이블 영역 (이름 고정 + 날짜 스크롤)
        table_area = QHBoxLayout()
        table_area.setSpacing(0)
        table_area.setContentsMargins(0, 0, 0, 0)

        # 이름 테이블 (고정)
        self.name_table = QTableWidget()
        self.name_table.setColumnCount(1)
        self.name_table.setHorizontalHeaderLabels(["\n이름"])
        self.name_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.name_table.setFixedWidth(90)
        self.name_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.name_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.name_table.verticalHeader().setVisible(False)
        self.name_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection)
        self.name_table.setAlternatingRowColors(False)
        table_area.addWidget(self.name_table)

        # 날짜 테이블 (스크롤)
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table_area.addWidget(self.table)

        layout.addLayout(table_area)

        # 수직 스크롤 동기화
        self.table.verticalScrollBar().valueChanged.connect(
            self.name_table.verticalScrollBar().setValue)
        self.name_table.verticalScrollBar().valueChanged.connect(
            self.table.verticalScrollBar().setValue)

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

        # 이름 테이블
        self.name_table.setRowCount(len(self.nurses))

        # 날짜 테이블
        self.table.clear()
        self.table.setRowCount(len(self.nurses))
        self.table.setColumnCount(num_days)

        # 헤더: 날짜만
        headers = []
        for d in range(1, num_days + 1):
            dt = self.start_date + timedelta(days=d - 1)
            wd = dt.weekday()
            headers.append(f"{dt.month}/{dt.day}\n({weekday_names[wd]})")
        self.table.setHorizontalHeaderLabels(headers)

        header = self.table.horizontalHeader()
        for d in range(num_days):
            header.setSectionResizeMode(d, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(d, 78)

        # 요청 맵 (OR 요청은 리스트로 수집)
        req_map = {}  # (nurse_id, day) → str or list[str]
        for r in self.requests:
            key = (r.nurse_id, r.day)
            if r.is_or:
                if key not in req_map or isinstance(req_map[key], list):
                    req_map.setdefault(key, [])
                    req_map[key].append(r.code)
            else:
                req_map[key] = r.code

        # 데이터 채우기
        for row, nurse in enumerate(self.nurses):
            # 이름 (고정 테이블)
            name_item = QTableWidgetItem(nurse.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.name_table.setItem(row, 0, name_item)

            for d in range(1, num_days + 1):
                raw = req_map.get((nurse.id, d), "")
                # OR 요청 → "D/휴가" 형태로 합침
                if isinstance(raw, list):
                    code = "/".join(raw)
                else:
                    code = raw
                wd = (self.start_date + timedelta(days=d - 1)).weekday()

                combo = NoWheelComboBox()
                combo.addItems(REQUEST_CODES)
                # OR 슬래시 코드는 임시 항목으로 추가
                if "/" in code:
                    combo.addItem(code)
                combo.setStyleSheet("font-size: 9pt; border: none;")

                if code and (code in REQUEST_CODES or "/" in code):
                    combo.setCurrentText(code)

                # 배경색
                self._apply_combo_style(combo, code, wd)

                combo.currentTextChanged.connect(
                    lambda text, r=row, c=d: self._on_request_changed(r, c, text)
                )
                self.table.setCellWidget(row, d - 1, combo)

            self.name_table.setRowHeight(row, 30)
            self.table.setRowHeight(row, 30)

        # ── 일요일 컬럼 구분선 적용 ──
        sunday_cols = set()
        for d in range(1, num_days + 1):
            if (self.start_date + timedelta(days=d - 1)).weekday() == 6:
                sunday_cols.add(d - 1)  # 0-based column index

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

        # 요청 리스트 업데이트 (기존 해당 날짜 요청 제거)
        self.requests = [
            r for r in self.requests
            if not (r.nurse_id == nurse.id and r.day == day)
        ]
        if code:
            if "/" in code:
                # 슬래시 코드 → OR 요청으로 분리 저장
                for part in code.split("/"):
                    part = part.strip()
                    if part:
                        self.requests.append(
                            Request(nurse_id=nurse.id, day=day, code=part, is_or=True)
                        )
            else:
                self.requests.append(Request(nurse_id=nurse.id, day=day, code=code))

    def _save_requests(self):
        self.dm.save_requests(self.requests, self.start_date)
        QMessageBox.information(self, "저장", "요청사항이 저장되었습니다.")

    def get_requests(self) -> list[Request]:
        return self.requests
