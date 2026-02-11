"""Tab 1: 설정 + 간호사 관리 — 응급실"""
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QHeaderView, QAbstractItemView,
    QMessageBox, QFileDialog, QLineEdit, QDateEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QIntValidator
from engine.models import Nurse, DataManager
from ui.styles import ROLE_OPTIONS, GRADE_OPTIONS, WEEKDAY_OPTIONS, FONT_FAMILY, NoWheelComboBox

# 테이블 열 인덱스
COL_NAME = 0
COL_ROLE = 1
COL_GRADE = 2
COL_PREGNANT = 3
COL_MALE = 4
COL_4DAY = 5
COL_WEEKOFF = 6
COL_VACATION = 7
COL_PREV_N = 8
COL_SLEEP = 9
COL_NOTE = 10
NUM_COLS = 11


class SetupTab(QWidget):
    nurses_changed = pyqtSignal()

    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.dm = data_manager
        self.nurses: list[Nurse] = []
        self._building = False
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── 상단: 시작일 선택 ──
        date_group = QGroupBox("스케줄 기본 설정")
        date_layout = QHBoxLayout(date_group)

        date_layout.addWidget(QLabel("시작일:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate(2026, 3, 1))
        self.date_edit.setFixedWidth(140)
        self.date_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.date_edit)

        self.period_label = QLabel("")
        self.period_label.setStyleSheet("color: #013976; font-weight: bold;")
        date_layout.addWidget(self.period_label)

        self.date_edit.dateChanged.connect(self._on_date_changed)
        self._on_date_changed()  # 초기 라벨 설정

        date_layout.addStretch()
        layout.addWidget(date_group)

        # ── 중앙: 간호사 테이블 ──
        nurse_group = QGroupBox("간호사 목록")
        nurse_layout = QVBoxLayout(nurse_group)

        # 버튼 바
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("+ 간호사 추가")
        self.add_btn.clicked.connect(self._add_nurse)
        btn_layout.addWidget(self.add_btn)

        self.del_btn = QPushButton("선택 삭제")
        self.del_btn.setObjectName("dangerBtn")
        self.del_btn.clicked.connect(self._delete_nurse)
        btn_layout.addWidget(self.del_btn)

        self.save_btn = QPushButton("저장")
        self.save_btn.clicked.connect(self._save_data)
        btn_layout.addWidget(self.save_btn)

        self.import_btn = QPushButton("규칙 엑셀 불러오기")
        self.import_btn.setObjectName("secondaryBtn")
        self.import_btn.clicked.connect(self._import_rules_excel)
        btn_layout.addWidget(self.import_btn)

        self.import_req_btn = QPushButton("신청표 엑셀 불러오기")
        self.import_req_btn.setObjectName("secondaryBtn")
        self.import_req_btn.clicked.connect(self._import_request_excel)
        btn_layout.addWidget(self.import_req_btn)

        btn_layout.addStretch()

        self.count_label = QLabel("총 0명")
        self.count_label.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        btn_layout.addWidget(self.count_label)

        nurse_layout.addLayout(btn_layout)

        # 테이블
        self.table = QTableWidget()
        self.table.verticalHeader().setDefaultSectionSize(38)
        headers = [
            "이름", "역할", "직급", "임산부", "남자",
            "주4일제", "고정주휴", "휴가잔여", "전월N", "수면이월", "비고",
        ]
        self.table.setColumnCount(NUM_COLS)
        self.table.setHorizontalHeaderLabels(headers)

        
        # 이름 
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(COL_NAME, 60)

        
        # 역할, 직급
        for col in [COL_ROLE, COL_GRADE]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(col, 100)

        # 체크박스 영역
        for col in [COL_PREGNANT, COL_MALE, COL_4DAY, COL_SLEEP]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(col, 65)

        header.setSectionResizeMode(COL_WEEKOFF, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_WEEKOFF, 80)

        for col in [COL_VACATION, COL_PREV_N]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(col, 65)

        # 비고는 늘어나게
        header.setSectionResizeMode(COL_NOTE, QHeaderView.ResizeMode.Stretch)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.cellChanged.connect(self._on_cell_changed)

        nurse_layout.addWidget(self.table)
        layout.addWidget(nurse_group)

        # ── 하단 안내 ──
        info_label = QLabel(
            "💡 '규칙 엑셀 불러오기': 근무표_규칙.xlsx (이름, 역할, 직급, 특수조건)\n"
            "💡 '신청표 엑셀 불러오기': 근무신청표.xlsx (이름 + 요청사항 + 고정 주휴 자동 감지)"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt; padding: 8px;")
        layout.addWidget(info_label)

    # ══════════════════════════════════════════
    # 데이터 관리
    # ══════════════════════════════════════════

    def _load_data(self):
        self.nurses = self.dm.load_nurses()
        self._rebuild_table()

    def _save_data(self):
        self._sync_from_table()
        self.dm.save_nurses(self.nurses)
        QMessageBox.information(self, "저장", "간호사 목록이 저장되었습니다.")

    def _add_nurse(self):
        new_id = max([n.id for n in self.nurses], default=0) + 1
        nurse = Nurse(id=new_id, name=f"간호사{new_id}")
        self.nurses.append(nurse)
        self._rebuild_table()

    def _delete_nurse(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        if not rows:
            QMessageBox.warning(self, "선택 없음", "삭제할 간호사를 선택하세요.")
            return
        reply = QMessageBox.question(
            self, "삭제 확인", f"{len(rows)}명을 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for row in rows:
                if row < len(self.nurses):
                    self.nurses.pop(row)
            self._rebuild_table()

    # ══════════════════════════════════════════
    # 테이블 빌드
    # ══════════════════════════════════════════

    def _rebuild_table(self):
        self._building = True
        self.table.setRowCount(len(self.nurses))

        for row, nurse in enumerate(self.nurses):
            # 이름
            self.table.setItem(row, COL_NAME, QTableWidgetItem(nurse.name))

            # 역할 콤보
            role_combo = NoWheelComboBox()
            role_combo.addItems(ROLE_OPTIONS)
            if nurse.role in ROLE_OPTIONS:
                role_combo.setCurrentText(nurse.role)
            elif nurse.role:
                role_combo.addItem(nurse.role)
                role_combo.setCurrentText(nurse.role)
            self.table.setCellWidget(row, COL_ROLE, role_combo)

            # 직급 콤보
            grade_combo = NoWheelComboBox()
            grade_combo.addItems(GRADE_OPTIONS)
            if nurse.grade in GRADE_OPTIONS:
                grade_combo.setCurrentText(nurse.grade)
            self.table.setCellWidget(row, COL_GRADE, grade_combo)

            # 임산부 체크
            cb_preg = QCheckBox()
            cb_preg.setChecked(nurse.is_pregnant)
            cb_preg.setStyleSheet("padding-left: 18px;")
            self.table.setCellWidget(row, COL_PREGNANT, cb_preg)

            # 남자 체크
            cb_male = QCheckBox()
            cb_male.setChecked(nurse.is_male)
            cb_male.setStyleSheet("padding-left: 18px;")
            self.table.setCellWidget(row, COL_MALE, cb_male)

            # 주4일제 체크
            cb_4day = QCheckBox()
            cb_4day.setChecked(nurse.is_4day_week)
            cb_4day.setStyleSheet("padding-left: 18px;")
            self.table.setCellWidget(row, COL_4DAY, cb_4day)

            # 고정 주휴 콤보
            weekoff_combo = QComboBox()
            weekoff_combo.addItems(WEEKDAY_OPTIONS)
            if nurse.fixed_weekly_off is not None:
                weekoff_combo.setCurrentIndex(nurse.fixed_weekly_off + 1)
            self.table.setCellWidget(row, COL_WEEKOFF, weekoff_combo)

            # 휴가 잔여 (일반 숫자 입력)
            vac_item = QTableWidgetItem(
                str(nurse.vacation_days) if nurse.vacation_days else ""
            )
            vac_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, COL_VACATION, vac_item)

            # 전월 N (일반 숫자 입력)
            prev_item = QTableWidgetItem(
                str(nurse.prev_month_N) if nurse.prev_month_N else ""
            )
            prev_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, COL_PREV_N, prev_item)

            # 수면 이월
            cb_sleep = QCheckBox()
            cb_sleep.setChecked(nurse.pending_sleep)
            cb_sleep.setStyleSheet("padding-left: 18px;")
            self.table.setCellWidget(row, COL_SLEEP, cb_sleep)

            # 비고
            self.table.setItem(row, COL_NOTE, QTableWidgetItem(nurse.note))

        self.count_label.setText(f"총 {len(self.nurses)}명")
        self._building = False

    def _on_cell_changed(self, row, col):
        if self._building or row >= len(self.nurses):
            return
        if col == COL_NAME:
            self.nurses[row].name = self.table.item(row, COL_NAME).text()
        elif col == COL_VACATION:
            item = self.table.item(row, COL_VACATION)
            try:
                self.nurses[row].vacation_days = int(item.text()) if item and item.text().strip() else 0
            except ValueError:
                pass
        elif col == COL_PREV_N:
            item = self.table.item(row, COL_PREV_N)
            try:
                self.nurses[row].prev_month_N = int(item.text()) if item and item.text().strip() else 0
            except ValueError:
                pass
        elif col == COL_NOTE:
            item = self.table.item(row, COL_NOTE)
            self.nurses[row].note = item.text() if item else ""

    def _sync_from_table(self):
        """테이블 위젯 → Nurse 객체 동기화"""
        for row, nurse in enumerate(self.nurses):
            item = self.table.item(row, COL_NAME)
            if item:
                nurse.name = item.text()

            combo = self.table.cellWidget(row, COL_ROLE)
            if combo:
                nurse.role = combo.currentText()

            combo = self.table.cellWidget(row, COL_GRADE)
            if combo:
                nurse.grade = combo.currentText()

            cb = self.table.cellWidget(row, COL_PREGNANT)
            if cb:
                nurse.is_pregnant = cb.isChecked()

            cb = self.table.cellWidget(row, COL_MALE)
            if cb:
                nurse.is_male = cb.isChecked()

            cb = self.table.cellWidget(row, COL_4DAY)
            if cb:
                nurse.is_4day_week = cb.isChecked()

            combo = self.table.cellWidget(row, COL_WEEKOFF)
            if combo:
                idx = combo.currentIndex()
                nurse.fixed_weekly_off = (idx - 1) if idx > 0 else None

            item = self.table.item(row, COL_VACATION)
            if item and item.text().strip():
                try:
                    nurse.vacation_days = int(item.text())
                except ValueError:
                    pass

            item = self.table.item(row, COL_PREV_N)
            if item and item.text().strip():
                try:
                    nurse.prev_month_N = int(item.text())
                except ValueError:
                    pass

            cb = self.table.cellWidget(row, COL_SLEEP)
            if cb:
                nurse.pending_sleep = cb.isChecked()

            item = self.table.item(row, COL_NOTE)
            nurse.note = item.text() if item else ""

    # ══════════════════════════════════════════
    # 엑셀 불러오기
    # ══════════════════════════════════════════

    def _import_rules_excel(self):
        """근무표_규칙.xlsx에서 간호사 속성 불러오기"""
        path, _ = QFileDialog.getOpenFileName(
            self, "근무표 규칙 엑셀 선택", "", "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            from engine.excel_io import import_nurse_rules
            imported = import_nurse_rules(path)
            if not imported:
                QMessageBox.warning(self, "오류", "간호사 데이터를 찾을 수 없습니다.")
                return

            reply = QMessageBox.question(
                self, "불러오기",
                f"{len(imported)}명을 불러왔습니다.\n기존 목록을 대체하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.nurses = imported
                self._rebuild_table()
                QMessageBox.information(self, "완료", f"{len(imported)}명 불러오기 완료")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"불러오기 실패:\n{str(e)}")

    def _import_request_excel(self):
        """근무신청표에서 이름 + 요청사항 + 고정주휴 불러오기"""
        path, _ = QFileDialog.getOpenFileName(
            self, "근무신청표 엑셀 선택", "", "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            from engine.excel_io import import_requests, import_nurses_from_request

            # 간호사가 없으면 신청표에서 이름 추출
            if not self.nurses:
                names = import_nurses_from_request(path)
                if names:
                    self.nurses = [
                        Nurse(id=i + 1, name=n) for i, n in enumerate(names)
                    ]
                    self._rebuild_table()

            if not self.nurses:
                QMessageBox.warning(self, "오류", "간호사 목록이 없습니다. 먼저 규칙 엑셀을 불러오세요.")
                return

            start_date = self.get_start_date()
            reqs, weekly_map = import_requests(path, self.nurses, start_date)

            # 고정 주휴 반영
            for nurse in self.nurses:
                if nurse.id in weekly_map:
                    nurse.fixed_weekly_off = weekly_map[nurse.id]

            self._rebuild_table()

            # 요청 저장
            if reqs:
                self.dm.save_requests(reqs, start_date)

            QMessageBox.information(
                self, "완료",
                f"요청 {len(reqs)}건 불러오기 완료\n"
                f"고정 주휴 {len(weekly_map)}명 감지\n\n"
                f"'요청사항' 탭에서 확인하세요."
            )
        except Exception as e:
            QMessageBox.critical(self, "오류", f"불러오기 실패:\n{str(e)}")

    # ══════════════════════════════════════════
    # 외부 인터페이스
    # ══════════════════════════════════════════

    def _on_date_changed(self):
        sd = self.get_start_date()
        ed = sd + timedelta(days=27)
        self.period_label.setText(
            f"▶ {sd.strftime('%Y.%m.%d')} ~ {ed.strftime('%Y.%m.%d')} (28일)"
        )

    def get_nurses(self) -> list[Nurse]:
        self._sync_from_table()
        return self.nurses

    def get_start_date(self) -> date:
        qd = self.date_edit.date()
        return date(qd.year(), qd.month(), qd.day())
