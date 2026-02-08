"""Tab 1: 설정 + 간호사 관리"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QHeaderView, QAbstractItemView,
    QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from engine.models import Nurse, DataManager
from ui.styles import SKILL_LEVELS, FIXED_SHIFT_OPTIONS, FONT_FAMILY


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

        # ── 상단: 월 선택 ──
        month_group = QGroupBox("스케줄 기본 설정")
        month_layout = QHBoxLayout(month_group)

        month_layout.addWidget(QLabel("스케줄 작성:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2024, 2040)
        self.year_spin.setValue(2026)
        self.year_spin.setSuffix("년")
        month_layout.addWidget(self.year_spin)

        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setValue(2)
        self.month_spin.setSuffix("월")
        month_layout.addWidget(self.month_spin)

        month_layout.addStretch()
        layout.addWidget(month_group)

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

        self.import_btn = QPushButton("엑셀에서 불러오기")
        self.import_btn.setObjectName("secondaryBtn")
        self.import_btn.clicked.connect(self._import_from_excel)
        btn_layout.addWidget(self.import_btn)

        btn_layout.addStretch()

        self.count_label = QLabel("총 0명")
        self.count_label.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        btn_layout.addWidget(self.count_label)

        nurse_layout.addLayout(btn_layout)

        # 테이블
        self.table = QTableWidget()
        headers = ["이름", "숙련도", "Day", "Eve", "Night", "고정근무", "프리셉터 대상", "비고"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 50)
        self.table.setColumnWidth(3, 50)
        self.table.setColumnWidth(4, 50)
        self.table.setColumnWidth(5, 100)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        self.table.cellChanged.connect(self._on_cell_changed)

        nurse_layout.addWidget(self.table)
        layout.addWidget(nurse_group)

        # ── 하단: 프리셉터 매핑 안내 ──
        info_label = QLabel(
            "💡 프리셉터 매핑: '프리셉터 대상' 열에서 신규 간호사 이름을 선택하면, "
            "두 사람이 반드시 같은 근무에 배정됩니다."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt; padding: 8px;")
        layout.addWidget(info_label)

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
        self.nurses_changed.emit()

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
            self.nurses_changed.emit()

    def _rebuild_table(self):
        self._building = True
        self.table.setRowCount(len(self.nurses))

        nurse_names = ["없음"] + [n.name for n in self.nurses]

        for row, nurse in enumerate(self.nurses):
            # 이름
            self.table.setItem(row, 0, QTableWidgetItem(nurse.name))

            # 숙련도 콤보
            skill_combo = QComboBox()
            for level, label in SKILL_LEVELS.items():
                skill_combo.addItem(f"{level} ({label})", level)
            skill_combo.setCurrentIndex(nurse.skill_level - 1)
            self.table.setCellWidget(row, 1, skill_combo)

            # D/E/N 체크박스
            for col, attr in [(2, "can_day"), (3, "can_evening"), (4, "can_night")]:
                cb = QCheckBox()
                cb.setChecked(getattr(nurse, attr))
                cb.setStyleSheet("margin-left: 15px;")
                self.table.setCellWidget(row, col, cb)

            # 고정근무
            fixed_combo = QComboBox()
            fixed_combo.addItems(FIXED_SHIFT_OPTIONS)
            if nurse.fixed_shift:
                idx = FIXED_SHIFT_OPTIONS.index(nurse.fixed_shift) if nurse.fixed_shift in FIXED_SHIFT_OPTIONS else 0
                fixed_combo.setCurrentIndex(idx)
            self.table.setCellWidget(row, 5, fixed_combo)

            # 평일만
            wd_cb = QCheckBox()
            wd_cb.setChecked(nurse.weekday_only)
            wd_cb.setStyleSheet("margin-left: 15px")
            self.table.setCellWidget(row, 6, wd_cb)

            # 프리셉터 대상
            preceptor_combo = QComboBox()
            preceptor_combo.addItems(nurse_names)
            if nurse.preceptor_of is not None:
                target = next((n.name for n in self.nurses if n.id == nurse.preceptor_of), None)
                if target and target in nurse_names:
                    preceptor_combo.setCurrentText(target)
            self.table.setCellWidget(row, 7, preceptor_combo)

            # 비고
            self.table.setItem(row, 8, QTableWidgetItem(nurse.note))

        self.count_label.setText(f"총 {len(self.nurses)}명")
        self._building = False

    def _on_cell_changed(self, row, col):
        if self._building or row >= len(self.nurses):
            return
        if col == 0:
            self.nurses[row].name = self.table.item(row, 0).text()
            # 프리셉터 콤보 업데이트
            self._rebuild_table()
        elif col == 7:
            item = self.table.item(row, 7)
            self.nurses[row].note = item.text() if item else ""

    def _sync_from_table(self):
        """테이블 위젯에서 데이터 동기화"""
        for row, nurse in enumerate(self.nurses):
            # 이름
            item = self.table.item(row, 0)
            if item:
                nurse.name = item.text()

            # 숙련도
            combo = self.table.cellWidget(row, 1)
            if combo:
                nurse.skill_level = combo.currentData()

            # D/E/N
            for col, attr in [(2, "can_day"), (3, "can_evening"), (4, "can_night")]:
                cb = self.table.cellWidget(row, col)
                if cb:
                    setattr(nurse, attr, cb.isChecked())

            # 고정근무
            fixed = self.table.cellWidget(row, 5)
            if fixed:
                val = fixed.currentText()
                nurse.fixed_shift = val if val != "없음" else None

            # 평일만
            wd_cb = self.table.cellWidget(row, 6)
            if wd_cb:
                nurse.weekday_only = wd_cb.isChecked()

            # 프리셉터 대상
            prec = self.table.cellWidget(row, 7)
            if prec:
                target_name = prec.currentText()
                if target_name == "없음":
                    nurse.preceptor_of = None
                else:
                    target = next((n for n in self.nurses if n.name == target_name), None)
                    nurse.preceptor_of = target.id if target else None

            # 비고
            item = self.table.item(row, 8)
            nurse.note = item.text() if item else ""

    def get_nurses(self) -> list[Nurse]:
        self._sync_from_table()
        return self.nurses

    def get_year_month(self) -> tuple[int, int]:
        return self.year_spin.value(), self.month_spin.value()

    def _import_from_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "엑셀 파일 선택", "", "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            from engine.excel_io import import_nurses, import_requests, _detect_format
            from openpyxl import load_workbook

            imported = import_nurses(path)
            if imported:
                reply = QMessageBox.question(
                    self, "불러오기",
                    f"{len(imported)}명을 불러왔습니다.\n"
                    "기존 목록을 대체하시겠습니까?\n\n"
                    "'아니오'를 선택하면 기존 목록에 추가합니다.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return
                if reply == QMessageBox.StandardButton.Yes:
                    self.nurses = imported
                else:
                    max_id = max([n.id for n in self.nurses], default=0)
                    for n in imported:
                        max_id += 1
                        n.id = max_id
                    self.nurses.extend(imported)
                self._rebuild_table()
                self.nurses_changed.emit()

                # 달력 격자 형식이면 요청사항도 불러올지 확인
                year, month = self.get_year_month()
                req_reply = QMessageBox.question(
                    self, "요청사항 불러오기",
                    f"이 파일에서 {year}년 {month}월 요청사항(희망근무)도\n"
                    "함께 불러오시겠습니까?\n\n"
                    "(파일에 D, E, N, OFF 등의 데이터가 있는 경우)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if req_reply == QMessageBox.StandardButton.Yes:
                    reqs = import_requests(path, self.nurses, year, month)
                    if reqs:
                        self.dm.save_requests(reqs, year, month)
                        QMessageBox.information(
                            self, "완료",
                            f"간호사 {len(imported)}명 + 요청사항 {len(reqs)}건 불러오기 완료\n\n"
                            "'요청사항' 탭에서 확인하세요."
                        )
                    else:
                        QMessageBox.information(
                            self, "완료",
                            f"간호사 {len(imported)}명 불러오기 완료\n"
                            "(요청사항 데이터는 없었습니다)"
                        )
                else:
                    QMessageBox.information(self, "완료", f"{len(imported)}명 불러오기 완료")
            else:
                QMessageBox.warning(self, "오류", "간호사 데이터를 찾을 수 없습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"불러오기 실패:\n{str(e)}")