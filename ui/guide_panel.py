"""가이드 사이드 패널 — 탭별 맥락 도움말"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel
from PyQt6.QtCore import Qt


# ──────────────────────────────────────
# 공통 HTML 스타일
# ──────────────────────────────────────
_CSS = """
<style>
body { font-family: '맑은 고딕', sans-serif; font-size: 10pt; color: #222; }
h2 { color: #013976; font-size: 12pt; margin: 14px 0 6px 0; border-bottom: 2px solid #013976; padding-bottom: 3px; }
h3 { color: #013976; font-size: 10.5pt; margin: 12px 0 4px 0; }
table { border-collapse: collapse; width: 100%; margin: 4px 0 8px 0; }
td { padding: 3px 6px; font-size: 9.5pt; vertical-align: top; }
tr:nth-child(even) { background: #f5f7fa; }
.code { background: #eef2f8; padding: 1px 5px; border-radius: 3px; font-weight: 600; }
.chip { display: inline-block; padding: 1px 7px; border-radius: 4px; font-weight: 600; font-size: 9pt; }
.chip-work { background: #fff; border: 1px solid #ccc; }
.chip-off  { background: #fcfb92; border: 1px solid #e0df60; }
.chip-excl { background: #ffd6d6; border: 1px solid #e0a0a0; }
.tip { background: #eef6ff; border-left: 3px solid #013976; padding: 6px 8px; margin: 6px 0; font-size: 9pt; border-radius: 0 4px 4px 0; }
.warn { background: #fff8e1; border-left: 3px solid #e6a800; padding: 6px 8px; margin: 6px 0; font-size: 9pt; border-radius: 0 4px 4px 0; }
ul { margin: 4px 0; padding-left: 18px; }
li { margin: 2px 0; font-size: 9.5pt; }
</style>
"""


def _wrap(body: str) -> str:
    return f"<html><head>{_CSS}</head><body>{body}</body></html>"


# ──────────────────────────────────────
# 탭 0: 설정
# ──────────────────────────────────────
_TAB0_SETUP = _wrap("""
<h2>설정 탭</h2>
<p>간호사 명단과 속성을 관리합니다.</p>

<h3>컬럼 설명</h3>
<table>
<tr><td><b>이름</b></td><td>간호사 이름 (필수)</td></tr>
<tr><td><b>비고1 (역할)</b></td><td>책임만, 외상, 혼자 관찰, 혼자관찰불가, 급성구역, 준급성, 격리구역, 중2 등</td></tr>
<tr><td><b>비고2 (직급)</b></td><td>책임, 서브차지 — D/E/N 시간대별 최소 인원 체크에 사용</td></tr>
<tr><td><b>임산부</b></td><td>체크 시 연속 근무 4일 초과 제한 + 4근무마다 POFF 1일 자동 배정</td></tr>
<tr><td><b>남자</b></td><td>체크 시 생휴 배정 제외</td></tr>
<tr><td><b>주4일제</b></td><td>체크 시 주 4일 근무 적용</td></tr>
<tr><td><b>고정주휴</b></td><td>매주 특정 요일에 고정 휴무 배정</td></tr>
<tr><td><b>휴가잔여</b></td><td>이번 달 사용 가능한 잔여 휴가 일수</td></tr>
<tr><td><b>전월N</b></td><td>지난 달 N 근무 횟수 (수면 발생 계산에 사용)</td></tr>
<tr><td><b>수면이월</b></td><td>전월 미사용 수면 이월 여부 (체크 = 1일 이월)</td></tr>
</table>

<h3>엑셀 불러오기</h3>
<table>
<tr><td><b>규칙 불러오기</b></td><td>근무표_규칙.xlsx에서 간호사 설정 일괄 반영</td></tr>
<tr><td><b>신청표 불러오기</b></td><td>신청표 엑셀에서 간호사 이름 추출</td></tr>
<tr><td><b>이전 근무 불러오기</b></td><td>전월 근무표에서 전월N·수면이월·마지막 근무 자동 반영</td></tr>
</table>

<div class="tip">
<b>팁:</b> 전월N과 수면이월은 직접 입력보다 <b>이전 근무 불러오기</b>를 사용하면 정확합니다.
</div>
""")


# ──────────────────────────────────────
# 탭 1: 요청사항
# ──────────────────────────────────────
_TAB1_REQUEST = _wrap("""
<h2>요청사항 탭</h2>
<p>간호사별·날짜별 근무/휴무 요청을 입력합니다.</p>

<h3>근무 코드</h3>
<table>
<tr><td><span class="chip chip-work">D</span></td><td>주간 근무 (Day)</td></tr>
<tr><td><span class="chip chip-work">E</span></td><td>저녁 근무 (Evening)</td></tr>
<tr><td><span class="chip chip-work">N</span></td><td>야간 근무 (Night)</td></tr>
<tr><td><span class="chip chip-work">중2</span></td><td>중간 근무 (평일만, 역할 "중2"만 가능)</td></tr>
</table>

<h3>휴무 코드</h3>
<table>
<tr><td><span class="chip chip-off">OFF</span></td><td>일반 휴무 (주당 1개, 4일근무 주당 2개)</td></tr>
<tr><td><span class="chip chip-off">주</span></td><td>주휴 (고정주휴 요일에 자동 배정)</td></tr>
<tr><td><span class="chip chip-off">법휴</span></td><td>법정 공휴일 휴무</td></tr>
<tr><td><span class="chip chip-off">생휴</span></td><td>생리 휴가 (여성만, 월 1회)</td></tr>
<tr><td><span class="chip chip-off">수면</span></td><td>수면 보상 휴무 (N 근무 기준 자동 계산)</td></tr>
<tr><td><span class="chip chip-off">휴가</span></td><td>연차 휴가</td></tr>
<tr><td><span class="chip chip-off">병가</span></td><td>병가</td></tr>
<tr><td><span class="chip chip-off">특휴</span></td><td>특별 휴가</td></tr>
<tr><td><span class="chip chip-off">공가</span></td><td>공가</td></tr>
<tr><td><span class="chip chip-off">경가</span></td><td>경조 휴가</td></tr>
<tr><td><span class="chip chip-off">보수</span></td><td>보수 교육</td></tr>
<tr><td><span class="chip chip-off">필수</span></td><td>필수 휴무</td></tr>
<tr><td><span class="chip chip-off">번표</span></td><td>번표 휴무</td></tr>
</table>

<h3>제외 코드</h3>
<table>
<tr><td><span class="chip chip-excl">D 제외</span></td><td>D 근무 배정하지 않음</td></tr>
<tr><td><span class="chip chip-excl">E 제외</span></td><td>E 근무 배정하지 않음</td></tr>
<tr><td><span class="chip chip-excl">N 제외</span></td><td>N 근무 배정하지 않음</td></tr>
</table>

<h3>OR 요청</h3>
<p>슬래시(/)로 구분하여 복수 요청 가능</p>
<div class="tip">
예: <span class="code">D/휴가</span> → D 또는 휴가 중 하나 배정
</div>

<div class="warn">
<b>주의:</b><br>
• 생휴는 여성만, 월 1회까지<br>
• '주'는 고정주휴 요일에만 유효<br>
• OFF는 주당 1개(4일근무 2개) 초과 시 무시됨<br>
• 빈칸 = 솔버가 자동 배정
</div>
""")


# ──────────────────────────────────────
# 탭 2: 규칙설정
# ──────────────────────────────────────
_TAB2_RULES = _wrap("""
<h2>규칙설정 탭</h2>
<p>근무표 생성 시 적용할 제약 조건을 설정합니다.</p>

<h3>일별 최소 인원</h3>
<ul>
<li><b>D / E / N 최소</b> — 각 시간대별 필요 최소 근무 인원</li>
<li><b>중2 최소</b> — 평일 중간 근무 인원 (주말 0)</li>
</ul>

<h3>직급 요건</h3>
<ul>
<li><b>책임 최소</b> — D/E/N 시간대에 '책임' 직급 최소 인원</li>
<li><b>서브차지 최소</b> — D/E/N 시간대에 책임+서브차지 합계 최소 인원</li>
</ul>

<h3>연속 근무 제한</h3>
<ul>
<li><b>최대 연속 근무</b> — N일 초과 연속 근무 금지 (기본 5)</li>
<li><b>최대 연속 야간</b> — N일 초과 연속 N 근무 금지 (기본 3)</li>
<li><b>월 최대 야간</b> — 한 달 N 근무 상한 (기본 6)</li>
</ul>

<h3>근무 순서 규칙</h3>
<ul>
<li>근무 순서: D(1) → 중2(2) → E(3) → N(4)</li>
<li>역순 전환 금지 (예: N→D 불가)</li>
<li>NN 후 최소 2일 휴무 보장</li>
</ul>

<h3>수면 발생 조건</h3>
<table>
<tr><td><b>월별 기준</b></td><td>N ≥ 7회 → 수면 1일 발생 (기본값)</td></tr>
<tr><td><b>2개월 기준</b></td><td>짝수 달: 전월N + 당월N ≥ 11회 → 추가 수면</td></tr>
</table>
<div class="tip">
<b>2개월 페어:</b> (1-2월), (3-4월), (5-6월) … 형태로 묶여 계산됩니다.
홀수 달 미사용 수면은 짝수 달로 이월됩니다.
</div>

<h3>임산부 규칙</h3>
<ul>
<li>연속 근무 4일 초과 금지</li>
<li>4근무마다 POFF 1일 자동 배정</li>
</ul>

<h3>주간 OFF / 법정 공휴일</h3>
<ul>
<li><b>주간 최소 OFF</b> — 7일 중 최소 휴무 일수 (기본 1)</li>
<li><b>법정 공휴일</b> — 해당 날짜에 법휴 배정 가능</li>
</ul>
""")


# ──────────────────────────────────────
# 탭 3: 결과
# ──────────────────────────────────────
_TAB3_RESULT = _wrap("""
<h2>결과 탭</h2>
<p>생성된 근무표를 확인하고 수정합니다.</p>

<h3>색상 범례</h3>
<table>
<tr>
  <td style="background:#ffff66; padding:3px 10px; border:1px solid #cccc00; text-align:center;">셀</td>
  <td>노란 배경 = 요청 반영됨</td>
</tr>
<tr>
  <td style="background:#ffffff; border:2px solid red; padding:3px 10px; text-align:center;">셀</td>
  <td>흰 배경 + 빨간 테두리 = 요청 미반영 (툴팁으로 원래 요청 표시)</td>
</tr>
<tr>
  <td style="background:#ffffff; padding:3px 10px; border:1px solid #ddd; text-align:center;">셀</td>
  <td>흰 배경 = 요청 없음 (자동 배정)</td>
</tr>
<tr>
  <td style="color:#d61506; font-weight:bold; padding:3px 10px; text-align:center;">N</td>
  <td>빨간 글자 = 야간 근무</td>
</tr>
<tr>
  <td style="background:#f2f2f2; padding:3px 10px; border:1px solid #ddd; text-align:center;">토/일</td>
  <td>회색 배경 = 주말</td>
</tr>
<tr>
  <td style="background:#DAEEFF; padding:3px 10px; border:1px solid #aaccee; text-align:center;">행</td>
  <td>하늘색 배경 = 이름 클릭 시 행 하이라이트</td>
</tr>
</table>

<h3>셀 수정</h3>
<ul>
<li>셀을 더블클릭하여 근무 변경 가능</li>
<li>변경 시 규칙 위반 여부를 자동 검사</li>
<li>위반 시 경고 팝업 → 확인하면 강제 반영 가능</li>
</ul>

<h3>컬럼 구성</h3>
<table>
<tr><td><b>이름</b></td><td>간호사 이름 (클릭 시 행 하이라이트)</td></tr>
<tr><td><b>휴가잔여</b></td><td>잔여 연차 (이번 달 사용 후)</td></tr>
<tr><td><b>잔여수면</b></td><td>= (N기준 발생 + 이월분) - 사용분</td></tr>
<tr><td><b>날짜</b></td><td>28일 주기로 근무 배정</td></tr>
<tr><td><b>통계</b></td><td>D/E/N/중2/OFF 등 횟수 합계</td></tr>
</table>

<h3>하단 정보</h3>
<ul>
<li><b>일별 인원 집계</b> — 각 날짜별 D/E/N/중2/OFF 인원 수</li>
<li><b>부족 인원 표시</b> — 최소 인원 미달 시 빨간 배경</li>
<li><b>위반 상세</b> — 규칙 위반 내역 목록</li>
</ul>

<h3>내보내기</h3>
<div class="tip">
<b>엑셀 내보내기</b> 버튼으로 근무표 + 통계를 xlsx 파일로 저장할 수 있습니다.
노란 배경(요청 반영) / 빨간 테두리(요청 미반영) 색상도 함께 내보내집니다.
</div>
""")

_TABS = [_TAB0_SETUP, _TAB1_REQUEST, _TAB2_RULES, _TAB3_RESULT]


# ──────────────────────────────────────
# GuidePanel 위젯
# ──────────────────────────────────────
class GuidePanel(QWidget):
    """탭에 따라 맥락별 도움말을 표시하는 패널."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setOpenExternalLinks(False)
        self._label.setStyleSheet("padding: 8px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._label)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: white; }"
        )
        layout.addWidget(scroll)

        self.set_tab(0)

    def set_tab(self, index: int):
        if 0 <= index < len(_TABS):
            self._label.setText(_TABS[index])
