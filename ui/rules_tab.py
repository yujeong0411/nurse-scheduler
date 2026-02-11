"""Tab 3: 규칙 설정 — 응급실"""
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QCheckBox, QPushButton, QFormLayout, QMessageBox,
    QScrollArea, QFrame, QLineEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
from engine.models import Rules, DataManager


class RulesTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.dm = data_manager
        self.rules = Rules()
        self._start_date = date(2026, 1, 1)
        self._init_ui()
        self._load_rules()

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # ── 일일 인원 배치 ──
        staff_group = QGroupBox("일일 최소 인원")
        staff_layout = QHBoxLayout(staff_group)
        self.daily_d = self._spin(7)
        self.daily_e = self._spin(8)
        self.daily_n = self._spin(7)
        # self.daily_m = self._spin(0)  # 중간근무 추가 시
        for label, spin in [
            ("D:", self.daily_d),
            # ("M (중간):", self.daily_m),  # 중간근무 추가 시
            ("E:", self.daily_e),
            ("N:", self.daily_n),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(140)
            row.addWidget(lbl)
            row.addWidget(spin)
            row.addWidget(QLabel("명"))
            row.addStretch()
            staff_layout.addLayout(row)
        layout.addWidget(staff_group)

        # ── 근무 순서 / 연속 제한 ──
        consec_group = QGroupBox("근무 순서 / 연속 제한")
        consec_layout = QFormLayout(consec_group)

        self.ban_reverse = QCheckBox("역순 금지 (D→중간→E→N 순서만 허용)")
        self.ban_reverse.setChecked(True)
        consec_layout.addRow(self.ban_reverse)

        self.max_consec_work = self._spin(5)
        consec_layout.addRow("최대 연속 근무:", self._spin_row(self.max_consec_work, "일"))

        self.max_consec_n = self._spin(3)
        consec_layout.addRow("최대 연속 N:", self._spin_row(self.max_consec_n, "개"))

        self.off_after_2n = self._spin(2)
        consec_layout.addRow("N 2연속 후 휴무:", self._spin_row(self.off_after_2n, "일"))

        self.max_n_month = self._spin(6)
        consec_layout.addRow("월 최대 N:", self._spin_row(self.max_n_month, "개"))

        layout.addWidget(consec_group)

        # ── 휴무 ──
        off_group = QGroupBox("휴무")
        off_layout = QFormLayout(off_group)

        self.min_weekly_off = self._spin(2)
        off_layout.addRow("주당 최소 휴무:", self._spin_row(self.min_weekly_off, "일"))

        layout.addWidget(off_group)

        # ── 직급 ──
        grade_group = QGroupBox("직급 제약")
        grade_layout = QFormLayout(grade_group)

        self.min_chief = self._spin(1)
        grade_layout.addRow("매 근무 책임 최소:", self._spin_row(self.min_chief, "명"))

        self.min_senior = self._spin(2)
        grade_layout.addRow("매 근무 책임+서브차지 최소:", self._spin_row(self.min_senior, "명"))

        self.max_junior = self._spin(3)
        grade_layout.addRow("매 근무 일반 최대 (권고):", self._spin_row(self.max_junior, "명"))

        layout.addWidget(grade_group)

        # ── 특수 조건 ──
        special_group = QGroupBox("특수 조건")
        special_layout = QFormLayout(special_group)

        self.preg_interval = self._spin(4)
        special_layout.addRow("임산부 연속 근무 제한:", self._spin_row(self.preg_interval, "일"))

        self.menstrual = QCheckBox("생리휴무 (남자 제외, 월 1개)")
        self.menstrual.setChecked(True)
        special_layout.addRow(self.menstrual)

        layout.addWidget(special_group)

        # ── 수면 ──
        sleep_group = QGroupBox("수면 휴무 발생 조건")
        sleep_layout = QFormLayout(sleep_group)

        self.sleep_monthly = self._spin(7)
        sleep_layout.addRow("당월 N ≥:", self._spin_row(self.sleep_monthly, "개 → 수면 발생"))

        self.sleep_bimonthly = self._spin(11)
        sleep_layout.addRow("2개월 합산 N ≥:", self._spin_row(self.sleep_bimonthly, "개 → 수면 발생"))

        layout.addWidget(sleep_group)

        # ── 법정공휴일 ──
        holiday_group = QGroupBox("법정공휴일 (해당 월 날짜, 쉼표 구분)")
        holiday_layout = QHBoxLayout(holiday_group)
        self.holidays_input = QLineEdit()
        self.holidays_input.setPlaceholderText("예: 1, 3, 15")
        self.holidays_input.setMinimumWidth(300)
        holiday_layout.addWidget(self.holidays_input)

        auto_btn = QPushButton("자동 감지")
        auto_btn.setToolTip("holidays 패키지로 해당 월 공휴일 자동 입력")
        auto_btn.clicked.connect(self._auto_detect_holidays)
        holiday_layout.addWidget(auto_btn)

        holiday_layout.addStretch()
        layout.addWidget(holiday_group)

        # ── 버튼 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("규칙 저장")
        save_btn.clicked.connect(self._save_rules)
        btn_layout.addWidget(save_btn)

        reset_btn = QPushButton("기본값 복원")
        reset_btn.setObjectName("secondaryBtn")
        reset_btn.clicked.connect(self._reset_rules)
        btn_layout.addWidget(reset_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _spin(self, default):
        edit = QLineEdit()
        edit.setValidator(QIntValidator(0, 31))
        edit.setText(str(default))
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit.setFixedWidth(60)
        return edit

    def _spin_row(self, spin, unit):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(spin)
        h.addWidget(QLabel(unit))
        h.addStretch()
        return w

    def _load_rules(self):
        self.rules = self.dm.load_rules()
        self._apply_to_ui()

    def _apply_to_ui(self):
        r = self.rules
        self.daily_d.setText(str(r.daily_D))
        self.daily_e.setText(str(r.daily_E))
        self.daily_n.setText(str(r.daily_N))
        self.ban_reverse.setChecked(r.ban_reverse_order)

        self.max_consec_work.setText(str(r.max_consecutive_work))
        self.max_consec_n.setText(str(r.max_consecutive_N))
        self.off_after_2n.setText(str(r.off_after_2N))
        self.max_n_month.setText(str(r.max_N_per_month))
        self.min_weekly_off.setText(str(r.min_weekly_off))
        self.min_chief.setText(str(r.min_chief_per_shift))
        self.min_senior.setText(str(r.min_senior_per_shift))
        self.max_junior.setText(str(r.max_junior_per_shift))
        self.preg_interval.setText(str(r.pregnant_poff_interval))
        self.menstrual.setChecked(r.menstrual_leave)
        self.sleep_monthly.setText(str(r.sleep_N_monthly))
        self.sleep_bimonthly.setText(str(r.sleep_N_bimonthly))

        if r.public_holidays:
            self.holidays_input.setText(", ".join(str(d) for d in r.public_holidays))

    def _get_int(self, widget):
        return int(widget.text()) if widget.text() else 0

    def _sync_from_ui(self):
        # 공휴일 파싱
        holidays = []
        text = self.holidays_input.text().strip()
        if text:
            for part in text.split(","):
                part = part.strip()
                try:
                    d = int(part)
                    if 1 <= d <= 31:
                        holidays.append(d)
                except ValueError:
                    pass

        self.rules = Rules(
            daily_D=self._get_int(self.daily_d),
            daily_E=self._get_int(self.daily_e),
            daily_N=self._get_int(self.daily_n),
            ban_reverse_order=self.ban_reverse.isChecked(),
            max_consecutive_work=self._get_int(self.max_consec_work),
            max_consecutive_N=self._get_int(self.max_consec_n),
            off_after_2N=self._get_int(self.off_after_2n),
            max_N_per_month=self._get_int(self.max_n_month),
            min_weekly_off=self._get_int(self.min_weekly_off),
            min_chief_per_shift=self._get_int(self.min_chief),
            min_senior_per_shift=self._get_int(self.min_senior),
            max_junior_per_shift=self._get_int(self.max_junior),
            pregnant_poff_interval=self._get_int(self.preg_interval),
            menstrual_leave=self.menstrual.isChecked(),
            sleep_N_monthly=self._get_int(self.sleep_monthly),
            sleep_N_bimonthly=self._get_int(self.sleep_bimonthly),
            public_holidays=holidays,
        )

    def _save_rules(self):
        self._sync_from_ui()
        self.dm.save_rules(self.rules)
        QMessageBox.information(self, "저장", "규칙이 저장되었습니다.")

    def _reset_rules(self):
        reply = QMessageBox.question(
            self, "초기화", "모든 규칙을 기본값으로 되돌리시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.rules = Rules()
            self._apply_to_ui()

    def get_rules(self) -> Rules:
        self._sync_from_ui()
        return self.rules

    def set_start_date(self, start_date: date):
        """설정 탭에서 시작일 변경 시 호출"""
        self._start_date = start_date

    def _auto_detect_holidays(self):
        """holidays 패키지로 해당 기간 공휴일 자동 감지"""
        try:
            from engine.kr_holidays import get_holidays_for_period
            sd = self._start_date
            ed = sd + timedelta(days=27)
            hols = get_holidays_for_period(sd)
            if hols:
                days_str = ", ".join(str(d) for d, _ in hols)
                names = "\n".join(
                    f"  {d}일차 ({(sd + timedelta(days=d-1)).strftime('%m/%d')}): {name}"
                    for d, name in hols
                )
                self.holidays_input.setText(days_str)
                QMessageBox.information(
                    self, "공휴일 자동 감지",
                    f"{sd.strftime('%Y.%m.%d')} ~ {ed.strftime('%Y.%m.%d')} 공휴일:\n{names}\n\n"
                    "필요시 직접 수정 가능합니다."
                )
            else:
                self.holidays_input.clear()
                QMessageBox.information(
                    self, "공휴일 자동 감지",
                    f"{sd.strftime('%Y.%m.%d')} ~ {ed.strftime('%Y.%m.%d')} 기간에는 공휴일이 없습니다."
                )
        except ImportError:
            QMessageBox.warning(
                self, "패키지 미설치",
                "holidays 패키지가 필요합니다.\n\n"
                "pip install holidays\n또는\nuv add holidays"
            )
