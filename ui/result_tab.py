"""Tab 4: 결과 + 수동 수정 + 통계"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox,
    QProgressBar, QGroupBox, QComboBox, QFileDialog, QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QBrush
from engine.models import Nurse, Request, Rules, Schedule, DataManager
from ui.styles import SHIFT_COLORS, SHIFT_TEXT_COLORS, WEEKEND_BG, SHORTAGE_BG, FONT_FAMILY, SHIFT_TYPES
import calendar


class ResultTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.dm = data_manager
        self.schedule: Schedule | None = None
        self._building = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 상단 버튼
        top = QHBoxLayout()

        self.generate_btn = QPushButton("▶ 근무표 생성")
        self.generate_btn.setFont(QFont(FONT_FAMILY, 12, QFont.Weight.Bold))
        self.generate_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; padding: 12px 24px; font-size: 13pt; }"
            "QPushButton:hover { background-color: #2ecc71; }"
        )
        self.generate_btn.clicked.connect(self._on_generate)
        top.addWidget(self.generate_btn)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedWidth(200)
        top.addWidget(self.progress)

        top.addStretch()

        self.regenerate_btn = QPushButton("다시 생성")
        self.regenerate_btn.setObjectName("secondaryBtn")
        self.regenerate_btn.clicked.connect(self._on_generate)
        self.regenerate_btn.setVisible(False)
        top.addWidget(self.regenerate_btn)

        self.export_btn = QPushButton("엑셀로 저장")
        self.export_btn.clicked.connect(self._export_excel)
        self.export_btn.setVisible(False)
        top.addWidget(self.export_btn)

        layout.addLayout(top)

        # 결과 테이블
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table, stretch=3)

        # 하단: 통계
        self.stats_group = QGroupBox("통계")
        self.stats_group.setVisible(False)
        stats_layout = QVBoxLayout(self.stats_group)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)

        self.pattern_label = QLabel("")
        self.pattern_label.setWordWrap(True)
        self.pattern_label.setStyleSheet("color: #c0392b;")
        stats_layout.addWidget(self.pattern_label)

        layout.addWidget(self.stats_group, stretch=1)

        # 안내 라벨 (생성 전)
        self.placeholder = QLabel(
            "⬆ '근무표 생성' 버튼을 눌러 자동 생성하세요.\n\n"
            "설정, 요청사항, 규칙을 먼저 입력한 뒤 생성하면 됩니다."
        )
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setFont(QFont(FONT_FAMILY, 12))
        self.placeholder.setStyleSheet("color: #999; padding: 40px;")
        layout.addWidget(self.placeholder)

    def set_schedule_data(self, nurses, requests, rules, year, month):
        """메인 윈도우에서 데이터 전달"""
        self.nurses = nurses
        self.requests = requests
        self.rules = rules
        self.year = year
        self.month = month

    def _on_generate(self):
        if not hasattr(self, 'nurses') or not self.nurses:
            QMessageBox.warning(self, "오류", "간호사 목록이 비어있습니다.\n'설정' 탭에서 간호사를 추가하세요.")
            return

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indeterminate
        self.generate_btn.setEnabled(False)

        try:
            from engine.solver import solve_schedule
            self.schedule = solve_schedule(
                self.nurses, self.requests, self.rules,
                self.year, self.month
            )

            if self.schedule and self.schedule.schedule_data:
                self._display_schedule()
                self.dm.save_schedule(self.schedule.schedule_data, self.year, self.month)
                self.placeholder.setVisible(False)
                self.stats_group.setVisible(True)
                self.regenerate_btn.setVisible(True)
                self.export_btn.setVisible(True)
            else:
                QMessageBox.warning(
                    self, "생성 실패",
                    "제약조건을 만족하는 근무표를 찾을 수 없습니다.\n\n"
                    "가능한 해결 방법:\n"
                    "• 간호사 수가 최소 인원 합계보다 적은지 확인\n"
                    "• 금지 패턴이 너무 엄격하지 않은지 확인\n"
                    "• 고정 근무 / 연차가 너무 많지 않은지 확인"
                )
        except ImportError:
            QMessageBox.information(
                self, "개발 중",
                "스케줄링 엔진이 아직 연결되지 않았습니다.\n(Day 3에 구현 예정)"
            )
        except Exception as e:
            QMessageBox.critical(self, "오류", f"생성 중 오류 발생:\n{str(e)}")
        finally:
            self.progress.setVisible(False)
            self.generate_btn.setEnabled(True)

    def _display_schedule(self):
        self._building = True
        num_days = self.schedule.num_days
        nurses = self.schedule.nurses
        stat_cols = ["D", "E", "N", "OFF"]

        total_cols = 1 + num_days + len(stat_cols)
        total_rows = len(nurses) + 4  # +1 빈행 +3 집계행

        self.table.clear()
        self.table.setRowCount(total_rows)
        self.table.setColumnCount(total_cols)

        # 헤더
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        headers = ["이름"]
        for d in range(1, num_days + 1):
            wd = calendar.weekday(self.year, self.month, d)
            headers.append(f"{d}\n({weekday_names[wd]})")
        headers.extend(stat_cols)
        self.table.setHorizontalHeaderLabels(headers)

        # 컬럼 너비
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 80)
        for c in range(1, num_days + 1):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, 44)
        for c in range(num_days + 1, total_cols):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, 40)

        # 간호사별 데이터
        for row, nurse in enumerate(nurses):
            # 이름
            name_item = QTableWidgetItem(nurse.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setFont(QFont(FONT_FAMILY, 9, QFont.Weight.Bold))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, name_item)

            counts = {"D": 0, "E": 0, "N": 0, "OFF": 0}

            for d in range(1, num_days + 1):
                shift = self.schedule.get_shift(nurse.id, d)
                item = QTableWidgetItem(shift)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(QFont(FONT_FAMILY, 9, QFont.Weight.Bold))

                # 색상
                if shift in SHIFT_COLORS:
                    item.setBackground(QBrush(SHIFT_COLORS[shift]))
                if shift in SHIFT_TEXT_COLORS:
                    item.setForeground(QBrush(SHIFT_TEXT_COLORS[shift]))

                # 주말 배경 (shift 없을때)
                wd = calendar.weekday(self.year, self.month, d)
                if wd >= 5 and shift not in SHIFT_COLORS:
                    item.setBackground(QBrush(WEEKEND_BG))

                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, d, item)

                if shift in counts:
                    counts[shift] += 1

            # 통계 열
            for i, s in enumerate(stat_cols):
                stat_item = QTableWidgetItem(str(counts.get(s, 0)))
                stat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                stat_item.setFlags(stat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                stat_item.setFont(QFont(FONT_FAMILY, 9))
                self.table.setItem(row, num_days + 1 + i, stat_item)

            self.table.setRowHeight(row, 28)

        # 빈 행
        sep_row = len(nurses)
        for c in range(total_cols):
            item = QTableWidgetItem("")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(sep_row, c, item)
        self.table.setRowHeight(sep_row, 8)

        # 집계 행 (D/E/N 인원수)
        for si, shift_type in enumerate(["D", "E", "N"]):
            agg_row = len(nurses) + 1 + si
            label_item = QTableWidgetItem(f"{shift_type} 인원")
            label_item.setFont(QFont(FONT_FAMILY, 8, QFont.Weight.Bold))
            label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(agg_row, 0, label_item)

            for d in range(1, num_days + 1):
                count = self.schedule.get_staff_count(d, shift_type)
                item = QTableWidgetItem(str(count))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(QFont(FONT_FAMILY, 8, QFont.Weight.Bold))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # 인원 부족 시 빨간 배경
                is_weekend = self.schedule.is_weekend(d)
                min_req = self.rules.get_min_staff(shift_type, is_weekend)
                if count < min_req:
                    item.setBackground(QBrush(SHORTAGE_BG))
                    item.setForeground(QBrush(QColor(200, 0, 0)))

                self.table.setItem(agg_row, d, item)
            self.table.setRowHeight(agg_row, 24)

        self._update_stats()

        # 셀 변경 감지
        self.table.cellChanged.connect(self._on_cell_changed)
        self._building = False

    def _on_cell_changed(self, row, col):
        if self._building or not self.schedule:
            return
        if row >= len(self.schedule.nurses) or col < 1 or col > self.schedule.num_days:
            return

        nurse = self.schedule.nurses[row]
        day = col
        item = self.table.item(row, col)
        new_shift = item.text().upper().strip()

        if new_shift not in ("D", "E", "N", "OFF", ""):
            self._building = True
            old = self.schedule.get_shift(nurse.id, day)
            item.setText(old)
            self._building = False
            return

        if new_shift == "":
            new_shift = "OFF"

        # 위반 체크
        try:
            from engine.validator import validate_change
            violations = validate_change(self.schedule, nurse, day, new_shift, self.rules)
            if violations:
                msg = "⚠️ 규칙 위반:\n" + "\n".join(f"• {v}" for v in violations)
                reply = QMessageBox.warning(
                    self, "규칙 위반",
                    f"{msg}\n\n그래도 적용하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    self._building = True
                    old = self.schedule.get_shift(nurse.id, day)
                    item.setText(old)
                    self._building = False
                    return
        except ImportError:
            pass

        # 적용
        self.schedule.set_shift(nurse.id, day, new_shift)

        # 색상 업데이트
        self._building = True
        if new_shift in SHIFT_COLORS:
            item.setBackground(QBrush(SHIFT_COLORS[new_shift]))
        if new_shift in SHIFT_TEXT_COLORS:
            item.setForeground(QBrush(SHIFT_TEXT_COLORS[new_shift]))
        item.setText(new_shift)
        self._building = False

        self._refresh_aggregates()
        self._update_stats()

    def _refresh_aggregates(self):
        if not self.schedule:
            return
        self._building = True
        num_days = self.schedule.num_days
        nurses = self.schedule.nurses

        for si, shift_type in enumerate(["D", "E", "N"]):
            agg_row = len(nurses) + 1 + si
            for d in range(1, num_days + 1):
                count = self.schedule.get_staff_count(d, shift_type)
                item = self.table.item(agg_row, d)
                if item:
                    item.setText(str(count))
                    is_weekend = self.schedule.is_weekend(d)
                    min_req = self.rules.get_min_staff(shift_type, is_weekend)
                    if count < min_req:
                        item.setBackground(QBrush(SHORTAGE_BG))
                        item.setForeground(QBrush(QColor(200, 0, 0)))
                    else:
                        item.setBackground(QBrush(QColor(255, 255, 255)))
                        item.setForeground(QBrush(QColor(0, 0, 0)))

        # 개인 통계 업데이트
        stat_cols = ["D", "E", "N", "OFF"]
        for row, nurse in enumerate(nurses):
            for i, s in enumerate(stat_cols):
                count = self.schedule.get_day_count(nurse.id, s)
                item = self.table.item(row, num_days + 1 + i)
                if item:
                    item.setText(str(count))

        self._building = False

    def _update_stats(self):
        if not self.schedule:
            return

        nurses = self.schedule.nurses
        stats = {"D": [], "E": [], "N": [], "OFF": []}
        for nurse in nurses:
            for s in stats:
                stats[s].append(self.schedule.get_day_count(nurse.id, s))

        lines = []
        for s, counts in stats.items():
            if counts:
                avg = sum(counts) / len(counts)
                mn, mx = min(counts), max(counts)
                lines.append(f"{s}: 평균 {avg:.1f}  (최소 {mn} ~ 최대 {mx}, 편차 {mx-mn})")

        self.stats_label.setText("📊 " + "  |  ".join(lines))

        # 기피 패턴 분석
        patterns = self._find_bad_patterns()
        if patterns:
            self.pattern_label.setText("⚠️ 기피 패턴: " + ", ".join(f"{k} {v}건" for k, v in patterns.items()))
        else:
            self.pattern_label.setText("✅ 기피 패턴 없음")

    def _find_bad_patterns(self) -> dict:
        if not self.schedule:
            return {}
        patterns = {}
        num_days = self.schedule.num_days
        for nurse in self.schedule.nurses:
            for d in range(1, num_days):
                s1 = self.schedule.get_shift(nurse.id, d)
                s2 = self.schedule.get_shift(nurse.id, d + 1)
                # E→D
                if s1 == "E" and s2 == "D":
                    patterns["E→D"] = patterns.get("E→D", 0) + 1
                # N→D
                if s1 == "N" and s2 == "D":
                    patterns["N→D"] = patterns.get("N→D", 0) + 1
                # N→E
                if s1 == "N" and s2 == "E":
                    patterns["N→E"] = patterns.get("N→E", 0) + 1
            # NNN (3연속 야간)
            for d in range(1, num_days - 1):
                if all(self.schedule.get_shift(nurse.id, d+i) == "N" for i in range(3)):
                    patterns["NNN"] = patterns.get("NNN", 0) + 1
        return patterns

    def _export_excel(self):
        if not self.schedule:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", f"근무표_{self.year}_{self.month:02d}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if path:
            try:
                from engine.excel_io import export_schedule
                export_schedule(self.schedule, self.rules, path)
                QMessageBox.information(self, "저장 완료", f"저장되었습니다:\n{path}")
            except ImportError:
                QMessageBox.information(self, "개발 중", "엑셀 내보내기 기능은 Day 6에 구현 예정입니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 실패:\n{str(e)}")
