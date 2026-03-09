"""Tab 1: 설정 + 간호사 관리 — 응급실"""
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QHeaderView, QAbstractItemView,
    QMessageBox, QFileDialog, QLineEdit, QDateEdit, QDialog,
    QDialogButtonBox
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
        # 저장된 시작일 불러오기
        settings = self.dm.load_settings()
        saved = settings.get("start_date")
        if saved:
            try:
                sd = date.fromisoformat(saved)
                self.date_edit.setDate(QDate(sd.year, sd.month, sd.day))
            except (ValueError, TypeError):
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())

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

        self.prev_shift_btn = QPushButton("이전 근무 불러오기")
        self.prev_shift_btn.setObjectName("secondaryBtn")
        self.prev_shift_btn.clicked.connect(self._open_prev_shift_dialog)
        btn_layout.addWidget(self.prev_shift_btn)

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

        # 헤더 툴팁
        self.table.horizontalHeaderItem(COL_PREV_N).setToolTip(
            "직접 입력하거나, '이전 근무 불러오기'로\n이전 달 근무표 엑셀에서 자동 반영됩니다."
        )
        self.table.horizontalHeaderItem(COL_SLEEP).setToolTip(
            "직접 체크하거나, '이전 근무 불러오기'로\n이전 달 근무표 엑셀에서 자동 반영됩니다."
        )

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
            "💡 '신청표 엑셀 불러오기': 근무신청표.xlsx (이름 + 요청사항 + 고정 주휴 자동 감지)\n"
            "💡 '이전 근무 불러오기': 이전 달 근무표 엑셀 → 전월N, 수면이월 자동 반영"
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
            weekoff_combo = NoWheelComboBox()
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
            from engine.excel_io import import_requests, import_nurses_from_request, detect_file_month

            # 날짜 검증
            start_date = self.get_start_date()
            file_year, file_month = detect_file_month(path)

            if file_month is not None:
                # 날짜 탐지 성공 → 불일치 검사
                mismatch_parts = []
                if file_year and file_year != start_date.year:
                    mismatch_parts.append(
                        f"  연도: 파일 = {file_year}년,  설정 = {start_date.year}년"
                    )
                if file_month != start_date.month:
                    mismatch_parts.append(
                        f"  월: 파일 = {file_month}월,  설정 = {start_date.month}월"
                    )

                if mismatch_parts:
                    detail = "\n".join(mismatch_parts)
                    reply = QMessageBox.warning(
                        self, "날짜 불일치",
                        f"파일의 날짜와 설정된 시작일이 다릅니다.\n\n"
                        f"{detail}\n\n"
                        f"시작일을 조정하거나 파일을 확인해주세요.\n"
                        f"그래도 불러오시겠습니까?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return

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
        # 시작일 저장
        settings = self.dm.load_settings()
        settings["start_date"] = sd.isoformat()
        self.dm.save_settings(settings)

    def get_nurses(self) -> list[Nurse]:
        self._sync_from_table()
        return self.nurses

    def _open_prev_shift_dialog(self):
        """이전 근무 불러오기 팝업"""
        self._sync_from_table()
        if not self.nurses:
            QMessageBox.warning(self, "오류", "간호사 목록이 없습니다.")
            return
        rules = self.dm.load_rules()
        dlg = PrevShiftDialog(self.nurses, self.get_start_date(), rules, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._rebuild_table()
            self.dm.save_nurses(self.nurses)

    def get_start_date(self) -> date:
        qd = self.date_edit.date()
        return date(qd.year(), qd.month(), qd.day())


# ══════════════════════════════════════════
# 이전 근무 입력 다이얼로그
# ══════════════════════════════════════════

# 다이얼로그 콤보박스 옵션
PREV_SHIFT_CODES = [
    "", "D", "중2", "E", "N",
    "OFF", "주", "법휴", "수면", "생휴", "휴가", "특휴", "공가", "경가", "보수", "POFF",
]

TAIL_DAYS = 5


class PrevShiftDialog(QDialog):
    """이전 달 마지막 5일 근무 입력/수정 팝업"""

    def __init__(self, nurses: list[Nurse], start_date: date, rules=None, parent=None):
        super().__init__(parent)
        self.nurses = nurses
        self.start_date = start_date
        self.rules = rules
        prev_month = (start_date - timedelta(days=1)).month
        self.setWindowTitle(f"이전 달({prev_month}월) 근무 불러오기")
        self.setMinimumSize(600, 500)
        self._building = False
        self._init_ui()
        self._populate()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel("이전 달 마지막 5일의 근무를 입력하세요. (월 경계 제약조건에 사용)")
        info.setWordWrap(True)
        info.setStyleSheet("color: #013976; font-weight: bold; padding: 4px;")
        layout.addWidget(info)

        # 버튼 바
        top_btn = QHBoxLayout()

        self.excel_btn = QPushButton("엑셀 불러오기")
        self.excel_btn.setObjectName("secondaryBtn")
        self.excel_btn.clicked.connect(self._import_from_excel)
        top_btn.addWidget(self.excel_btn)

        self.clear_btn = QPushButton("초기화")
        self.clear_btn.setObjectName("dangerBtn")
        self.clear_btn.clicked.connect(self._clear_all)
        top_btn.addWidget(self.clear_btn)

        top_btn.addStretch()
        layout.addLayout(top_btn)

        # 테이블: 행=간호사, 열=이전 달 마지막 5일
        # 시작일 기준 이전 달 마지막 날짜 계산
        prev_last_date = self.start_date - timedelta(days=1)  # 이전 달 마지막 날
        prev_month = prev_last_date.month
        prev_last_day = prev_last_date.day
        self._tail_dates = []
        headers = []
        for i in range(TAIL_DAYS):
            d = prev_last_day - TAIL_DAYS + 1 + i
            self._tail_dates.append(d)
            headers.append(f"{prev_month}월 {d}일")

        self.table = QTableWidget()
        self.table.setRowCount(len(self.nurses))
        self.table.setColumnCount(TAIL_DAYS)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setVerticalHeaderLabels([n.name for n in self.nurses])
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        # 적용/취소
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("적용")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        btn_box.accepted.connect(self._apply)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _populate(self):
        """기존 prev_tail_shifts를 콤보박스에 채움"""
        self._building = True
        for row, nurse in enumerate(self.nurses):
            tail = nurse.prev_tail_shifts or []
            for col in range(TAIL_DAYS):
                combo = NoWheelComboBox()
                combo.addItems(PREV_SHIFT_CODES)
                if col < len(tail) and tail[col] in PREV_SHIFT_CODES:
                    combo.setCurrentText(tail[col])
                self.table.setCellWidget(row, col, combo)
        self._building = False

    def _apply(self):
        """콤보박스 값을 nurses에 저장"""
        for row, nurse in enumerate(self.nurses):
            shifts = []
            for col in range(TAIL_DAYS):
                combo = self.table.cellWidget(row, col)
                val = combo.currentText() if combo else ""
                shifts.append(val)
            nurse.prev_tail_shifts = shifts
        self.accept()

    def _clear_all(self):
        """전체 비우기"""
        self._building = True
        for row in range(self.table.rowCount()):
            for col in range(TAIL_DAYS):
                combo = self.table.cellWidget(row, col)
                if combo:
                    combo.setCurrentIndex(0)
        self._building = False

    def _import_from_excel(self):
        """엑셀 파일에서 이전 근무표 읽기"""
        path, _ = QFileDialog.getOpenFileName(
            self, "이전 달 근무표 엑셀 선택", "", "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            from engine.excel_io import import_prev_schedule, detect_file_month
            from engine.models import get_sleep_pair

            nurse_names = [n.name for n in self.nurses]
            tail_result, n_counts, sleep_counts = import_prev_schedule(path, nurse_names, TAIL_DAYS)

            if not tail_result:
                QMessageBox.warning(self, "오류", "매칭되는 간호사가 없습니다.")
                return

            # 수면이월 자동 판단을 위한 월 감지
            _, prev_month = detect_file_month(path)
            current_month = self.start_date.month
            sleep_auto_applied = False
            sleep_carry_count = 0

            if prev_month is not None and self.rules is not None:
                prev_pair = get_sleep_pair(prev_month)
                cur_pair = get_sleep_pair(current_month)
                # 이전 달이 홀수(페어 첫 달)이고, 현재 달이 같은 페어의 짝수 달
                can_carry = (prev_month == prev_pair[0]
                             and cur_pair == prev_pair
                             and current_month == prev_pair[1])
                sleep_auto_applied = True

                for nurse in self.nurses:
                    if nurse.name in n_counts:
                        n = n_counts[nurse.name]
                        sleep_used = sleep_counts.get(nurse.name, 0)
                        if can_carry and n >= self.rules.sleep_N_monthly and sleep_used == 0:
                            nurse.pending_sleep = True
                            sleep_carry_count += 1
                        else:
                            nurse.pending_sleep = False

            self._building = True
            matched = 0
            for row, nurse in enumerate(self.nurses):
                if nurse.name in tail_result:
                    matched += 1
                    shifts = tail_result[nurse.name]
                    for col in range(TAIL_DAYS):
                        combo = self.table.cellWidget(row, col)
                        if combo and col < len(shifts):
                            val = shifts[col]
                            idx = combo.findText(val)
                            if idx >= 0:
                                combo.setCurrentIndex(idx)
                            else:
                                combo.setCurrentIndex(0)
                if nurse.name in n_counts:
                    nurse.prev_month_N = n_counts[nurse.name]
            self._building = False

            # 완료 메시지 구성
            msg = (f"{matched}명 매칭 완료 (전체 {len(self.nurses)}명)\n"
                   f"전월 N 횟수 자동 반영 완료")
            if sleep_auto_applied:
                msg += f"\n수면이월 자동 판단: {sleep_carry_count}명 이월"
            else:
                msg += "\n수면이월: 월 감지 실패 → 수동 확인 필요"

            QMessageBox.information(self, "완료", msg)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"불러오기 실패:\n{str(e)}")
