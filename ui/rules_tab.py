"""Tab 3: 규칙 설정"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QSpinBox, QCheckBox, QPushButton, QFormLayout, QMessageBox,
    QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from engine.models import Rules, DataManager
from ui.styles import FONT_FAMILY


class RulesTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.dm = data_manager
        self.rules = Rules()
        self._init_ui()
        self._load_rules()

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # ── 인원 배치 ──
        staff_group = QGroupBox("인원 배치")
        staff_layout = QHBoxLayout(staff_group)

        # 평일
        weekday_box = QVBoxLayout()
        weekday_box.addWidget(QLabel("평일 최소 인원"))
        self.wd_day = self._spin(5, "Day")
        self.wd_eve = self._spin(5, "Evening")
        self.wd_night = self._spin(2, "Night")
        for label, spin in [("Day:", self.wd_day), ("Evening:", self.wd_eve), ("Night:", self.wd_night)]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(70)
            row.addWidget(lbl)
            row.addWidget(spin)
            weekday_box.addLayout(row)
        staff_layout.addLayout(weekday_box)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet("color: #cccccc;")
        staff_layout.addWidget(line)

        # 주말
        weekend_box = QVBoxLayout()
        weekend_box.addWidget(QLabel("주말 최소 인원"))
        self.we_day = self._spin(4, "Day")
        self.we_eve = self._spin(4, "Evening")
        self.we_night = self._spin(2, "Night")
        for label, spin in [("Day:", self.we_day), ("Evening:", self.we_eve), ("Night:", self.we_night)]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(70)
            row.addWidget(lbl)
            row.addWidget(spin)
            weekend_box.addLayout(row)
        staff_layout.addLayout(weekend_box)

        layout.addWidget(staff_group)

        # ── 금지 패턴 ──
        ban_group = QGroupBox("금지 패턴")
        ban_layout = QVBoxLayout(ban_group)
        self.ban_nd = QCheckBox("Night → Day 금지 (야간 다음날 주간 불가)")
        self.ban_ne = QCheckBox("Night → Evening 금지 (야간 다음날 저녁 불가)")
        self.ban_ed = QCheckBox("Evening → Day 금지 (저녁 다음날 주간 불가)")
        self.ban_nd.setChecked(True)
        self.ban_ne.setChecked(True)
        self.ban_ed.setChecked(True)
        ban_layout.addWidget(self.ban_nd)
        ban_layout.addWidget(self.ban_ne)
        ban_layout.addWidget(self.ban_ed)
        layout.addWidget(ban_group)

        # ── 연속 제한 ──
        consec_group = QGroupBox("연속 제한")
        consec_layout = QFormLayout(consec_group)
        self.max_consec_work = self._spin(5)
        self.max_consec_night = self._spin(3)
        self.night_off_after = self._spin(1)
        consec_layout.addRow("최대 연속 근무일:", self._spin_row(self.max_consec_work, "일"))
        consec_layout.addRow("최대 연속 야간:", self._spin_row(self.max_consec_night, "일"))
        consec_layout.addRow("야간 연속 후 OFF:", self._spin_row(self.night_off_after, "일"))
        layout.addWidget(consec_group)

        # ── 휴무 설정 ──
        off_group = QGroupBox("휴무 설정")
        off_layout = QFormLayout(off_group)
        self.min_off = self._spin(8)
        self.max_off = self._spin(20)
        self.max_consec_off = self._spin(5)
        off_layout.addRow("월 최소 휴무일:", self._spin_row(self.min_off, "일"))
        off_layout.addRow("월 최대 휴무일:", self._spin_row(self.max_off, "일"))
        off_layout.addRow("최대 연속 휴무:", self._spin_row(self.max_consec_off, "일"))
        layout.addWidget(off_group)

        # ── 팀 구성 ──
        team_group = QGroupBox("팀 구성 규칙")
        team_layout = QVBoxLayout(team_group)
        self.senior_all = QCheckBox("모든 근무에 숙련자(숙련도 3 이상) 1명 이상 필수")
        self.ban_newbie = QCheckBox("신규(숙련도 1) 끼리 같은 야간 배정 금지")
        self.senior_all.setChecked(True)
        self.ban_newbie.setChecked(True)
        team_layout.addWidget(self.senior_all)
        team_layout.addWidget(self.ban_newbie)
        layout.addWidget(team_group)

        # ── 저장 버튼 ──
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

    def _spin(self, default, suffix=""):
        spin = QSpinBox()
        spin.setRange(0, 31)
        spin.setValue(default)
        spin.setFixedWidth(70)
        return spin

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
        self.wd_day.setValue(r.weekday_min_day)
        self.wd_eve.setValue(r.weekday_min_evening)
        self.wd_night.setValue(r.weekday_min_night)
        self.we_day.setValue(r.weekend_min_day)
        self.we_eve.setValue(r.weekend_min_evening)
        self.we_night.setValue(r.weekend_min_night)
        self.ban_nd.setChecked(r.ban_night_to_day)
        self.ban_ne.setChecked(r.ban_night_to_evening)
        self.ban_ed.setChecked(r.ban_evening_to_day)
        self.max_consec_work.setValue(r.max_consecutive_work)
        self.max_consec_night.setValue(r.max_consecutive_night)
        self.night_off_after.setValue(r.night_off_after)
        self.min_off.setValue(r.min_monthly_off)
        self.max_off.setValue(r.max_monthly_off)
        self.max_consec_off.setValue(r.max_consecutive_off)
        self.senior_all.setChecked(r.senior_required_all)
        self.ban_newbie.setChecked(r.ban_newbie_pair_night)

    def _sync_from_ui(self):
        self.rules = Rules(
            weekday_min_day=self.wd_day.value(),
            weekday_min_evening=self.wd_eve.value(),
            weekday_min_night=self.wd_night.value(),
            weekend_min_day=self.we_day.value(),
            weekend_min_evening=self.we_eve.value(),
            weekend_min_night=self.we_night.value(),
            ban_night_to_day=self.ban_nd.isChecked(),
            ban_night_to_evening=self.ban_ne.isChecked(),
            ban_evening_to_day=self.ban_ed.isChecked(),
            max_consecutive_work=self.max_consec_work.value(),
            max_consecutive_night=self.max_consec_night.value(),
            night_off_after=self.night_off_after.value(),
            min_monthly_off=self.min_off.value(),
            max_monthly_off=self.max_off.value(),
            max_consecutive_off=self.max_consec_off.value(),
            senior_required_all=self.senior_all.isChecked(),
            ban_newbie_pair_night=self.ban_newbie.isChecked(),
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
