"""Tab 4: 결과 + 수동 수정 + 통계 — 응급실"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox,
    QProgressBar, QGroupBox, QFileDialog, QStyledItemDelegate
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QFont, QBrush, QPen
from engine.models import (
    Nurse, Request, Rules, Schedule, DataManager,
    WORK_SHIFTS, OFF_TYPES,
)
from ui.styles import (
    SHIFT_COLORS, SHIFT_TEXT_COLORS, SHIFT_TYPES,
    WEEKEND_BG, SHORTAGE_BG, FONT_FAMILY,
    WeekSeparatorDelegate,
)
import calendar


class WeekSeparatorDelegate(QStyledItemDelegate):
    """일요일 컬럼 왼쪽에 굵은 구분선을 그리는 델리게이트"""

    def __init__(self, sunday_cols: set[int], parent=None):
        super().__init__(parent)
        self.sunday_cols = sunday_cols

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.column() in self.sunday_cols:
            painter.save()
            pen = QPen(QColor(80, 80, 80))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(
                option.rect.left(), option.rect.top(),
                option.rect.left(), option.rect.bottom(),
            )
            painter.restore()


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

        # 하단 통계
        self.stats_group = QGroupBox("통계")
        self.stats_group.setVisible(False)
        stats_layout = QVBoxLayout(self.stats_group)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)

        self.grade_label = QLabel("")
        self.grade_label.setFont(QFont(FONT_FAMILY, 12, QFont.Weight.Bold))
        stats_layout.addWidget(self.grade_label)

        self.pattern_label = QLabel("")
        self.pattern_label.setWordWrap(True)
        self.pattern_label.setStyleSheet("color: #c0392b;")
        stats_layout.addWidget(self.pattern_label)

        # 감점 상세 토글
        self.detail_btn = QPushButton("📋 감점 상세 보기")
        self.detail_btn.setVisible(False)
        self.detail_btn.clicked.connect(self._toggle_deduction_detail)
        stats_layout.addWidget(self.detail_btn)

        self.deduction_label = QLabel("")
        self.deduction_label.setWordWrap(True)
        self.deduction_label.setStyleSheet(
            "color: #555; font-size: 9pt; padding: 6px; "
            "background: #f9f9f9; border-radius: 4px;"
        )
        self.deduction_label.setVisible(False)
        stats_layout.addWidget(self.deduction_label)

        layout.addWidget(self.stats_group, stretch=1)

        # 안내 라벨
        self.placeholder = QLabel(
            "⬆ '근무표 생성' 버튼을 눌러 자동 생성하세요.\n\n"
            "설정, 요청사항, 규칙을 먼저 입력한 뒤 생성하면 됩니다."
        )
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setFont(QFont(FONT_FAMILY, 12))
        self.placeholder.setStyleSheet("color: #999; padding: 40px;")
        layout.addWidget(self.placeholder)

    def set_schedule_data(self, nurses, requests, rules, year, month):
        self.nurses = nurses
        self.requests = requests
        self.rules = rules
        self.year = year
        self.month = month

    def _on_generate(self):
        if not hasattr(self, 'nurses') or not self.nurses:
            QMessageBox.warning(
                self, "오류",
                "간호사 목록이 비어있습니다.\n'설정' 탭에서 간호사를 추가하세요."
            )
            return

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
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
                    "• 확정 휴무가 너무 많지 않은지 확인\n"
                    "• 역할/직급 조건이 인원 대비 과하지 않은지 확인"
                )
        except ImportError:
            QMessageBox.information(
                self, "개발 중",
                "ortools가 설치되지 않았습니다.\npip install ortools 실행 후 다시 시도하세요."
            )
        except Exception as e:
            QMessageBox.critical(self, "오류", f"생성 중 오류 발생:\n{str(e)}")
        finally:
            self.progress.setVisible(False)
            self.generate_btn.setEnabled(True)

    # ══════════════════════════════════════════
    # 결과 표시
    # ══════════════════════════════════════════

    def _display_schedule(self):
        self._building = True
        self.table.blockSignals(True)  # cellChanged 시그널 차단
        num_days = self.schedule.num_days
        nurses = self.schedule.nurses
        stat_cols = ["D", "E", "N", "OFF", "총"]
        # 중간근무 추가 시: ["D", "M", "E", "N", "OFF", "총"]

        # 컬럼 레이아웃: 이름(0) + 휴가(1) + 생휴(2) + 수면(3) + 날짜(4~) + 통계
        EXTRA_COLS = 3  # 휴가, 생휴, 수면
        DAY_START = 1 + EXTRA_COLS  # = 4
        total_cols = 1 + EXTRA_COLS + num_days + len(stat_cols)
        total_rows = len(nurses) + 4  # +1 빈행 +3 집계행

        self.table.clear()
        self.table.setRowCount(total_rows)
        self.table.setColumnCount(total_cols)

        # 주 구분선: 일요일 컬럼 + 통계 열 앞에 굵은 세로선
        border_cols = set()
        for d in range(2, num_days + 1):
            if calendar.weekday(self.year, self.month, d) == 6:  # 일요일
                border_cols.add(DAY_START + d - 1)
        border_cols.add(DAY_START + num_days)  # 통계 열 구분
        self._week_delegate = WeekSeparatorDelegate(border_cols, self.table)
        self.table.setItemDelegate(self._week_delegate)

        # 헤더
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        headers = ["이름", "휴가", "생휴", "수면"]
        for d in range(1, num_days + 1):
            wd = calendar.weekday(self.year, self.month, d)
            headers.append(f"{d}\n({weekday_names[wd]})")
        headers.extend(stat_cols)
        self.table.setHorizontalHeaderLabels(headers)

        # 컬럼 너비
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 80)
        for c in range(1, DAY_START):  # 휴가/생휴/수면
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, 36)
        for c in range(DAY_START, DAY_START + num_days):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, 44)
        for c in range(DAY_START + num_days, total_cols):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, 36)

        # 주 구분선: 일요일 컬럼에 굵은 왼쪽 선
        monday_cols = set()
        for d in range(1, num_days + 1):
            if calendar.weekday(self.year, self.month, d) == 6:  # 일요일
                monday_cols.add(DAY_START + d - 1)
        self.table.setItemDelegate(
            WeekSeparatorDelegate(monday_cols, self.table)
        )

        # 간호사별 데이터
        for row, nurse in enumerate(nurses):
            # 이름
            name_item = QTableWidgetItem(nurse.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setFont(QFont(FONT_FAMILY, 9, QFont.Weight.Bold))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, name_item)

            # 휴가/생휴/수면 (읽기 전용)
            for ci, val in enumerate([
                str(nurse.vacation_days) if nurse.vacation_days else "",
                "",  # 생휴: 결과 표시 후 아래에서 계산
                "",  # 수면: 결과 표시 후 아래에서 계산
            ]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(QFont(FONT_FAMILY, 8))
                self.table.setItem(row, 1 + ci, item)

            d_cnt, e_cnt, n_cnt, off_cnt = 0, 0, 0, 0
            menst_cnt, sleep_cnt = 0, 0

            for d in range(1, num_days + 1):
                shift = self.schedule.get_shift(nurse.id, d)
                col = DAY_START + d - 1
                item = QTableWidgetItem(shift)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(QFont(FONT_FAMILY, 8, QFont.Weight.Bold))

                if shift in SHIFT_COLORS:
                    item.setBackground(QBrush(SHIFT_COLORS[shift]))
                if shift in SHIFT_TEXT_COLORS:
                    item.setForeground(QBrush(SHIFT_TEXT_COLORS[shift]))

                wd = calendar.weekday(self.year, self.month, d)
                if wd >= 5 and shift not in SHIFT_COLORS:
                    item.setBackground(QBrush(WEEKEND_BG))

                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

                if shift == "D":
                    d_cnt += 1
                elif shift == "E":
                    e_cnt += 1
                elif shift == "N":
                    n_cnt += 1
                else:
                    off_cnt += 1
                if shift == "생":
                    menst_cnt += 1
                if shift == "수면":
                    sleep_cnt += 1

            # 생휴/수면 카운트 업데이트
            self.table.item(row, 2).setText(str(menst_cnt) if menst_cnt else "")
            self.table.item(row, 3).setText(str(sleep_cnt) if sleep_cnt else "")

            total_work = d_cnt + e_cnt + n_cnt
            stat_vals = [d_cnt, e_cnt, n_cnt, off_cnt, total_work]
            stat_start = DAY_START + num_days
            for i, val in enumerate(stat_vals):
                stat_item = QTableWidgetItem(str(val))
                stat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                stat_item.setFlags(stat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                stat_item.setFont(QFont(FONT_FAMILY, 9))
                self.table.setItem(row, stat_start + i, stat_item)

            self.table.setRowHeight(row, 28)

        # 빈 행
        sep_row = len(nurses)
        for c in range(total_cols):
            item = QTableWidgetItem("")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(sep_row, c, item)
        self.table.setRowHeight(sep_row, 8)

        # 집계 행
        # 중간근무 추가 시: ["D", "M", "E", "N"]
        for si, shift_type in enumerate(["D", "E", "N"]):
            agg_row = len(nurses) + 1 + si
            label_item = QTableWidgetItem(f"{shift_type} 인원")
            label_item.setFont(QFont(FONT_FAMILY, 8, QFont.Weight.Bold))
            label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(agg_row, 0, label_item)

            for d in range(1, num_days + 1):
                col = DAY_START + d - 1
                count = sum(
                    1 for n in nurses
                    if self.schedule.get_shift(n.id, d) == shift_type
                )
                item = QTableWidgetItem(str(count))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(QFont(FONT_FAMILY, 8, QFont.Weight.Bold))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # 인원 부족 체크
                min_req = {
                    "D": self.rules.daily_D,
                    "E": self.rules.daily_E,
                    "N": self.rules.daily_N,
                }[shift_type]
                if count < min_req:
                    item.setBackground(QBrush(SHORTAGE_BG))
                    item.setForeground(QBrush(QColor(200, 0, 0)))

                self.table.setItem(agg_row, col, item)
            self.table.setRowHeight(agg_row, 24)

        self._update_stats()

        # 셀 변경 감지 (중복 연결 방지)
        try:
            self.table.cellChanged.disconnect(self._on_cell_changed)
        except TypeError:
            pass  # 아직 연결 안 됨
        self.table.cellChanged.connect(self._on_cell_changed)

        self.table.blockSignals(False)
        self._building = False

    # ══════════════════════════════════════════
    # 수동 수정
    # ══════════════════════════════════════════

    def _on_cell_changed(self, row, col):
        if self._building or not self.schedule:
            return
        # 날짜 컬럼: 4 ~ 4+num_days-1 (이름/휴가/생휴/수면 이후)
        DAY_START = 4
        num_days = self.schedule.num_days
        if row >= len(self.schedule.nurses):
            return
        if col < DAY_START or col >= DAY_START + num_days:
            return

        nurse = self.schedule.nurses[row]
        day = col - DAY_START + 1
        item = self.table.item(row, col)
        new_shift = item.text().strip()

        # 유효한 코드인지 확인
        if new_shift not in SHIFT_TYPES:
            self._building = True
            old = self.schedule.get_shift(nurse.id, day)
            item.setText(old)
            self._building = False
            return

        # 위반 체크
        try:
            from engine.validator import validate_change
            violations = validate_change(
                self.schedule, nurse, day, new_shift, self.rules
            )
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
        self.table.blockSignals(True)
        num_days = self.schedule.num_days
        nurses = self.schedule.nurses
        DAY_START = 4

        # 집계 행
        for si, shift_type in enumerate(["D", "E", "N"]):
            agg_row = len(nurses) + 1 + si
            min_req = {
                "D": self.rules.daily_D,
                "E": self.rules.daily_E,
                "N": self.rules.daily_N,
            }[shift_type]

            for d in range(1, num_days + 1):
                col = DAY_START + d - 1
                count = sum(
                    1 for n in nurses
                    if self.schedule.get_shift(n.id, d) == shift_type
                )
                item = self.table.item(agg_row, col)
                if item:
                    item.setText(str(count))
                    if count < min_req:
                        item.setBackground(QBrush(SHORTAGE_BG))
                        item.setForeground(QBrush(QColor(200, 0, 0)))
                    else:
                        item.setBackground(QBrush(QColor(255, 255, 255)))
                        item.setForeground(QBrush(QColor(0, 0, 0)))

        # 개인 통계 업데이트
        stat_start = DAY_START + num_days
        for row, nurse in enumerate(nurses):
            d_cnt = sum(
                1 for d in range(1, num_days + 1)
                if self.schedule.get_shift(nurse.id, d) == "D"
            )
            e_cnt = sum(
                1 for d in range(1, num_days + 1)
                if self.schedule.get_shift(nurse.id, d) == "E"
            )
            n_cnt = sum(
                1 for d in range(1, num_days + 1)
                if self.schedule.get_shift(nurse.id, d) == "N"
            )
            off_cnt = num_days - d_cnt - e_cnt - n_cnt
            total_work = d_cnt + e_cnt + n_cnt

            for i, val in enumerate([d_cnt, e_cnt, n_cnt, off_cnt, total_work]):
                item = self.table.item(row, stat_start + i)
                if item:
                    item.setText(str(val))

            # 생휴/수면 카운트 업데이트
            menst_cnt = sum(
                1 for d in range(1, num_days + 1)
                if self.schedule.get_shift(nurse.id, d) == "생"
            )
            sleep_cnt = sum(
                1 for d in range(1, num_days + 1)
                if self.schedule.get_shift(nurse.id, d) == "수면"
            )
            for ci, cnt in [(2, menst_cnt), (3, sleep_cnt)]:
                item = self.table.item(row, ci)
                if item:
                    item.setText(str(cnt) if cnt else "")

        self.table.blockSignals(False)
        self._building = False

    # ══════════════════════════════════════════
    # 통계
    # ══════════════════════════════════════════

    def _update_stats(self):
        if not self.schedule:
            return

        try:
            from engine.evaluator import evaluate_schedule
            result = evaluate_schedule(self.schedule, self.rules)

            self.grade_label.setText(
                f"📊 종합 점수: {result['score']}점 (등급 {result['grade']})"
            )

            lines = []
            lines.append(
                f"D 편차 {result['d_deviation']} | "
                f"E 편차 {result['e_deviation']} | "
                f"N 편차 {result['n_deviation']} | "
                f"주말 편차 {result['weekend_deviation']}"
            )

            req = result['request_fulfilled']
            lines.append(
                f"요청 반영 {req['fulfilled']}/{req['total']} ({req['rate']}%)"
            )

            if result['rule_violations'] > 0:
                lines.append(f"⚠️ 규칙 위반 {result['rule_violations']}건")

            self.stats_label.setText("  |  ".join(lines))

            # 역순 패턴
            bad = result.get("bad_patterns", {})
            if bad:
                self.pattern_label.setText(
                    "⚠️ 역순 패턴: " +
                    ", ".join(f"{k} {v}건" for k, v in bad.items())
                )
            else:
                self.pattern_label.setText("✅ 역순 패턴 없음")

            # 감점 상세
            deductions = result.get("deductions", [])
            if deductions:
                self.detail_btn.setVisible(True)
                lines = []
                for item_name, penalty, detail in deductions:
                    lines.append(f"▸ {item_name}: -{penalty}점")
                    lines.append(f"   {detail}")
                self._deduction_text = "\n".join(lines)
            else:
                self.detail_btn.setVisible(False)
                self.deduction_label.setVisible(False)
                self._deduction_text = ""

        except (ImportError, Exception):
            self.grade_label.setText("")
            self.stats_label.setText("")
            self.pattern_label.setText("")
            self.detail_btn.setVisible(False)
            self.deduction_label.setVisible(False)

    def _toggle_deduction_detail(self):
        """감점 상세 패널 토글"""
        if self.deduction_label.isVisible():
            self.deduction_label.setVisible(False)
            self.detail_btn.setText("📋 감점 상세 보기")
        else:
            self.deduction_label.setText(getattr(self, "_deduction_text", ""))
            self.deduction_label.setVisible(True)
            self.detail_btn.setText("📋 감점 상세 접기")

    def _export_excel(self):
        if not self.schedule:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장",
            f"근무표_{self.year}_{self.month:02d}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if path:
            try:
                from engine.excel_io import export_schedule
                export_schedule(self.schedule, self.rules, path)
                QMessageBox.information(self, "저장 완료", f"저장되었습니다:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 실패:\n{str(e)}")
