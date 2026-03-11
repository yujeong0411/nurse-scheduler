"""Tab 2: 요청사항 달력 — 응급실"""
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QBrush
from engine.models import Nurse, Request, Rules, DataManager, SHIFT_ORDER, WORK_SHIFTS
from ui.styles import (
    REQUEST_CODES,
    FONT_FAMILY, NoWheelComboBox, WeekSeparatorDelegate
)

_MID_AND_D = {"D", "D9", "D1", "중1", "중2"}
_WD_NAMES  = ["월", "화", "수", "목", "금", "토", "일"]

class RequestTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.dm = data_manager
        self.nurses: list[Nurse] = []
        self.start_date = date(2026, 3, 1)
        self.requests: list[Request] = []
        self.rules: Rules | None = None
        self._building = False
        self._highlighted_row = -1
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
        self.name_table.cellClicked.connect(self._on_name_clicked)
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

        # 수직 스크롤 동기화 (순환 방지 플래그)
        self._scroll_syncing = False
        self.table.verticalScrollBar().valueChanged.connect(self._sync_name_scroll)
        self.name_table.verticalScrollBar().valueChanged.connect(self._sync_table_scroll)

    def _sync_name_scroll(self, value):
        if not self._scroll_syncing:
            self._scroll_syncing = True
            self.name_table.verticalScrollBar().setValue(value)
            self._scroll_syncing = False

    def _sync_table_scroll(self, value):
        if not self._scroll_syncing:
            self._scroll_syncing = True
            self.table.verticalScrollBar().setValue(value)
            self._scroll_syncing = False

    def refresh(self, nurses: list[Nurse], start_date: date, rules: Rules | None = None):
        self.nurses = nurses
        self.start_date = start_date
        if rules is not None:
            self.rules = rules
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

        self._highlighted_row = -1
        self._building = False

    def _apply_combo_style(self, combo, code, weekday):
        """콤보박스에 코드에 맞는 색상 적용"""
        base = "font-size: 9pt; border: none; "
        if code:
            # 요청이 있으면 종류에 관계없이 노란색 (근무/휴무/중간근무/제외 모두)
            combo.setStyleSheet(base + "background-color: rgb(252, 251, 146);")
        elif weekday >= 5:
            combo.setStyleSheet(base + "background-color: #f2f2f2;")
        else:
            combo.setStyleSheet(base)

    def _get_combo_code(self, row: int, day: int) -> str:
        """day(1-based)의 현재 콤보 값 반환. 범위 밖이면 ""."""
        if day < 1 or day > 28:
            return ""
        combo = self.table.cellWidget(row, day - 1)
        return combo.currentText() if combo else ""

    def _validate_request(self, row: int, day: int, code: str, nurse: Nurse) -> str | None:
        """입력값 즉시 검증. 차단 메시지 반환 (None = 통과)."""
        g = lambda d: self._get_combo_code(row, d)  # 편의 alias

        # 1. 생휴: 남자 불가
        if code == "생휴" and nurse.is_male:
            return "남자 간호사는 생휴를 신청할 수 없습니다."

        # 2. 생휴: 여성 월 1회 초과
        if code == "생휴" and not nurse.is_male:
            already = sum(
                1 for r in self.requests
                if r.nurse_id == nurse.id and r.code == "생휴" and r.day != day
            )
            if already >= 1:
                return "생휴는 월 1회만 신청 가능합니다. 이미 다른 날에 생휴가 입력되어 있습니다."

        # 3a. POFF: 임산부만 가능
        if code == "POFF" and not nurse.is_pregnant:
            return "POFF는 임산부만 신청할 수 있습니다."

        # 3. 중2: role 제한
        if code == "중2" and nurse.role != "중2":
            return "중2 근무는 중2 역할 간호사만 신청할 수 있습니다."

        # 4. 중2: 평일 전용
        if code == "중2":
            wd = (self.start_date + timedelta(days=day - 1)).weekday()
            if wd >= 5:
                return f"중2 근무는 평일에만 신청 가능합니다. ({_WD_NAMES[wd]}요일 입력 불가)"

        # 5. 보수/필수/번표: 전날 N 금지 (H3c)
        if code in ("보수", "필수", "번표"):
            prev = g(day - 1)
            if prev == "N":
                return f"N 근무 다음날에는 {code}를 입력할 수 없습니다."
            # 전월 tail 경계
            if day == 1:
                tail = nurse.prev_tail_shifts
                if tail and tail[-1] == "N":
                    return f"전월 마지막 N 다음날에는 {code}를 입력할 수 없습니다."

        # 6. 역순: 전날 요청 → 오늘
        if code in SHIFT_ORDER:
            prev = g(day - 1)
            if prev in SHIFT_ORDER and SHIFT_ORDER[prev] > SHIFT_ORDER[code]:
                return f"역순 배치 불가: 전날 {prev}({SHIFT_ORDER[prev]}) → 오늘 {code}({SHIFT_ORDER[code]})"
            # 전월 tail 경계
            if day == 1:
                tail = nurse.prev_tail_shifts
                if tail and tail[-1] in SHIFT_ORDER and SHIFT_ORDER[tail[-1]] > SHIFT_ORDER[code]:
                    return f"역순 배치 불가: 전월 마지막 {tail[-1]} → 1일 {code}"

        # 7. 역순: 오늘 → 다음날 요청
        if code in SHIFT_ORDER:
            nxt = g(day + 1)
            if nxt in SHIFT_ORDER and SHIFT_ORDER[code] > SHIFT_ORDER[nxt]:
                return f"역순 배치 불가: 오늘 {code}({SHIFT_ORDER[code]}) → 다음날 {nxt}({SHIFT_ORDER[nxt]})"

        # 8. N→휴무→D/중간: 오늘이 D/중간이고 이틀 전 N, 전날 휴무
        if code in _MID_AND_D:
            prev1 = g(day - 1)
            prev2 = g(day - 2)
            if prev2 == "N" and prev1 and prev1 not in WORK_SHIFTS:
                return f"N→휴무→{code} 배치 불가: N 후 최소 2일 휴무가 필요합니다."
            # 전월 tail 경계 (day=2)
            if day == 2:
                tail = nurse.prev_tail_shifts
                if tail and tail[-1] == "N" and prev1 and prev1 not in WORK_SHIFTS:
                    return f"전월 N→{prev1}→{code} 배치 불가: N 후 최소 2일 휴무가 필요합니다."
            # 전월 tail 경계 (day=1)
            if day == 1:
                tail = nurse.prev_tail_shifts
                if tail:
                    if tail[-1] == "N":
                        return f"전월 마지막 N 직후 {code} 배치 불가: N 후 최소 2일 휴무가 필요합니다."
                    if len(tail) >= 2 and tail[-2] == "N" and tail[-1] not in WORK_SHIFTS:
                        return f"전월 N→휴무→{code} 배치 불가: N 후 최소 2일 휴무가 필요합니다."

        # 9. N→휴무→D/중간: 오늘이 휴무이고 전날 N, 다음날 D/중간 이미 입력됨
        if code and code not in WORK_SHIFTS:
            prev1 = g(day - 1)
            nxt1  = g(day + 1)
            if prev1 == "N" and nxt1 in _MID_AND_D:
                return f"N→{code}→{nxt1} 배치 불가: N 후 최소 2일 휴무가 필요합니다."
            # 전월 tail 경계 (day=1)
            if day == 1:
                tail = nurse.prev_tail_shifts
                if tail and tail[-1] == "N" and nxt1 in _MID_AND_D:
                    return f"전월 N→{code}→{nxt1} 배치 불가: N 후 최소 2일 휴무가 필요합니다."

        # 10. 고정 주휴일에 근무 입력
        if code in WORK_SHIFTS and nurse.fixed_weekly_off is not None:
            wd = (self.start_date + timedelta(days=day - 1)).weekday()
            if wd == nurse.fixed_weekly_off:
                return f"고정 주휴일({_WD_NAMES[wd]}요일)에는 근무를 신청할 수 없습니다."

        # 10c. OFF 주당 초과 입력
        if code == "OFF":
            max_off = 2 if nurse.is_4day_week else 1
            week = (day - 1) // 7
            already = sum(
                1 for r in self.requests
                if r.nurse_id == nurse.id and r.code == "OFF"
                and (r.day - 1) // 7 == week and r.day != day
            )
            if already >= max_off:
                return f"{week + 1}주차 OFF 요청이 최대 {max_off}개를 초과합니다. (현재 {already}개)"

        # 10b. 주휴를 고정 주휴일 아닌 날에 입력
        if code == "주" and nurse.fixed_weekly_off is not None:
            wd = (self.start_date + timedelta(days=day - 1)).weekday()
            if wd != nurse.fixed_weekly_off:
                return f"주휴는 고정 주휴일({_WD_NAMES[nurse.fixed_weekly_off]}요일)에만 신청할 수 있습니다. (현재: {_WD_NAMES[wd]}요일)"

        # 11. N 입력 시 다음날 보수/필수/번표 체크 (H3c 역방향)
        if code == "N":
            nxt = g(day + 1)
            if nxt in ("보수", "필수", "번표"):
                return f"N 다음날에 {nxt}가 있어 N을 입력할 수 없습니다."

        # 12. NN 후 2일 휴무 — 근무 입력 시
        if code in WORK_SHIFTS:
            prev1 = g(day - 1)
            prev2 = g(day - 2)
            prev3 = g(day - 3)
            # NN + 1off 뒤 근무 (오늘이 두 번째 필요 휴무 자리)
            if prev2 == "N" and prev3 == "N" and prev1 not in WORK_SHIFTS and prev1 != "":
                return "NN 후 2일 휴무가 필요합니다. (N→N→휴무→근무 불가)"
            # NN 바로 다음 근무 (오늘이 첫 번째 필요 휴무 자리)
            if prev1 == "N" and prev2 == "N":
                return "NN 후 2일 휴무가 필요합니다. (N→N 직후 근무 불가)"
            # 전월 tail 경계
            tail = nurse.prev_tail_shifts
            if tail:
                if day == 1 and len(tail) >= 2 and tail[-2] == "N" and tail[-1] == "N":
                    return "NN 후 2일 휴무가 필요합니다. (전월 N→N 직후 근무 불가)"
                if day == 2 and tail[-1] == "N" and g(1) == "N":
                    return "NN 후 2일 휴무가 필요합니다. (전월 N + 1일 N 이후 근무 불가)"
                if day == 1 and len(tail) >= 3 and tail[-3] == "N" and tail[-2] == "N" and tail[-1] not in WORK_SHIFTS:
                    return "NN 후 2일 휴무가 필요합니다. (전월 N→N→휴무 이후 근무 불가)"

        # 13. NN 확정 시 이후 2일에 이미 근무가 있으면 블록
        if code == "N":
            prev1 = g(day - 1)
            if prev1 == "N":  # 오늘까지 NN 확정
                nxt1 = g(day + 1)
                nxt2 = g(day + 2)
                if nxt1 in WORK_SHIFTS:
                    return f"NN 후 2일 휴무 필요: {day+1}일에 이미 {nxt1} 입력됨"
                if nxt2 in WORK_SHIFTS:
                    return f"NN 후 2일 휴무 필요: {day+2}일에 이미 {nxt2} 입력됨"
            # 전월 tail 경계: tail[-1]=N + 오늘=N → NN
            tail = nurse.prev_tail_shifts
            if tail and tail[-1] == "N" and day == 1:
                nxt1 = g(2)
                nxt2 = g(3)
                if nxt1 in WORK_SHIFTS:
                    return f"NN 후 2일 휴무 필요: 2일에 이미 {nxt1} 입력됨"
                if nxt2 in WORK_SHIFTS:
                    return f"NN 후 2일 휴무 필요: 3일에 이미 {nxt2} 입력됨"

        # 14. 연속 근무 초과 (H4)
        if code in WORK_SHIFTS and self.rules is not None:
            max_w = self.rules.max_consecutive_work
            count = 1
            # 뒤로 카운트 (전월 tail 포함)
            for d2 in range(day - 1, 0, -1):
                c2 = g(d2)
                if c2 in WORK_SHIFTS:
                    count += 1
                else:
                    break
            if day == 1:
                tail = nurse.prev_tail_shifts
                if tail:
                    for t in reversed(tail):
                        if t in WORK_SHIFTS:
                            count += 1
                        else:
                            break
            # 앞으로 카운트
            for d2 in range(day + 1, 29):
                c2 = g(d2)
                if c2 in WORK_SHIFTS:
                    count += 1
                else:
                    break
            if count > max_w:
                return f"연속 근무 {count}일: 최대 {max_w}일을 초과합니다."

        # 15. 연속 N 초과 (H5)
        if code == "N" and self.rules is not None:
            max_cn = self.rules.max_consecutive_N
            count = 1
            for d2 in range(day - 1, 0, -1):
                if g(d2) == "N":
                    count += 1
                else:
                    break
            if day == 1:
                tail = nurse.prev_tail_shifts
                if tail:
                    for t in reversed(tail):
                        if t == "N":
                            count += 1
                        else:
                            break
            for d2 in range(day + 1, 29):
                if g(d2) == "N":
                    count += 1
                else:
                    break
            if count > max_cn:
                return f"연속 N {count}개: 최대 {max_cn}개를 초과합니다."

        # 16. 월 N 최대 초과 (H7)
        if code == "N" and self.rules is not None:
            existing_N = sum(
                1 for r in self.requests
                if r.nurse_id == nurse.id and r.code == "N" and r.day != day
            )
            if existing_N >= self.rules.max_N_per_month:
                return f"월 N 요청이 최대 {self.rules.max_N_per_month}개를 초과합니다. (현재 {existing_N}개)"

        # 17. 법휴: 공휴일에만 (H10b)
        if code == "법휴" and self.rules is not None:
            if day not in self.rules.public_holidays:
                return f"{day}일은 공휴일이 아닙니다. 법휴는 공휴일에만 신청 가능합니다."

        return None  # 통과

    def _on_request_changed(self, row, day, code):
        if self._building or row >= len(self.nurses):
            return
        nurse = self.nurses[row]

        # ── 즉시 검증 ──
        if code:
            msg = self._validate_request(row, day, code, nurse)
            if msg:
                QMessageBox.warning(self, "입력 불가", msg)
                # 콤보 되돌리기 (building 플래그로 재귀 방지)
                self._building = True
                combo = self.table.cellWidget(row, day - 1)
                if combo:
                    combo.setCurrentText("")
                    wd = (self.start_date + timedelta(days=day - 1)).weekday()
                    self._apply_combo_style(combo, "", wd)
                self._building = False
                return

        # 스타일 업데이트 (day는 1-based, cellWidget은 0-based)
        combo = self.table.cellWidget(row, day - 1)
        if combo:
            wd = (self.start_date + timedelta(days=day - 1)).weekday()
            self._apply_combo_style(combo, code, wd)
            # 해당 행이 하이라이트 중이면 다시 적용
            if row == self._highlighted_row:
                combo.setStyleSheet(
                    "font-size: 9pt; border: none; background-color: #DAEEFF;"
                )

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

    _ROW_HIGHLIGHT = "#DAEEFF"  # 연한 하늘색

    def _on_name_clicked(self, row, col):
        """이름 셀 클릭 시 해당 행 하이라이트 토글"""
        if self._highlighted_row == row:
            self._apply_row_highlight(row, False)
            self._highlighted_row = -1
        else:
            if self._highlighted_row >= 0:
                self._apply_row_highlight(self._highlighted_row, False)
            self._highlighted_row = row
            self._apply_row_highlight(row, True)

    def _apply_row_highlight(self, row: int, on: bool):
        """행 전체에 하이라이트 적용/해제"""
        # 이름 셀
        name_item = self.name_table.item(row, 0)
        if name_item:
            name_item.setBackground(
                QBrush(QColor(self._ROW_HIGHLIGHT)) if on else QBrush(QColor("#FFFFFF"))
            )
        # 날짜 콤보박스들
        num_days = self.table.columnCount()
        for col in range(num_days):
            combo = self.table.cellWidget(row, col)
            if combo is None:
                continue
            if on:
                combo.setStyleSheet(
                    f"font-size: 9pt; border: none; background-color: {self._ROW_HIGHLIGHT};"
                )
            else:
                wd = (self.start_date + timedelta(days=col)).weekday()
                # 해당 콤보의 현재 코드를 읽어 원래 색상 복원
                code = combo.currentText()
                self._apply_combo_style(combo, code, wd)

    def _save_requests(self):
        self.dm.save_requests(self.requests, self.start_date)
        QMessageBox.information(self, "저장", "요청사항이 저장되었습니다.")

    def get_requests(self) -> list[Request]:
        return self.requests
