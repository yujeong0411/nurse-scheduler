"""사용 가이드 다이얼로그 — Modern Design Edition"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QScrollArea, QCheckBox, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QCursor


def _scroll_label(html: str) -> QScrollArea:
    """HTML 내용을 담은 스크롤 가능한 QLabel 위젯 생성"""
    label = QLabel(html)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    label.setTextFormat(Qt.TextFormat.RichText)
    # QLabel 자체에는 패딩과 배경색을 주어 종이 질감 연출
    label.setStyleSheet(
        "QLabel { padding: 24px 32px; font-size: 14px; font-family: '맑은 고딕', 'Malgun Gothic', sans-serif; "
        "color: #2d3748; background: white; line-height: 1.6; }"
    )
    label.setOpenExternalLinks(True)

    scroll = QScrollArea()
    scroll.setWidget(label)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    # 스크롤 영역 배경은 흰색으로 통일
    scroll.setStyleSheet("QScrollArea { background: white; border: none; }")
    return scroll


# ══════════════════════════════════════════
# HTML 콘텐츠 (CSS 디자인 시스템 적용)
# ══════════════════════════════════════════

_CSS = """
<style>
/* 기본 타이포그래피 */
body { color: #2d3748; font-family: '맑은 고딕'; }
h2 { color: #1a365d; margin-top: 10px; margin-bottom: 15px; font-size: 18pt; 
     border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; font-weight: bold; }
h3 { color: #2b6cb0; margin-top: 24px; margin-bottom: 10px; font-size: 13pt; font-weight: bold; }
p { margin-bottom: 10px; line-height: 1.6; }

/* 테이블 스타일 */
table { border-collapse: separate; border-spacing: 0; margin: 12px 0 20px 0; 
        border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0; width: 100%; }
th { background: linear-gradient(180deg, #f7fafc, #edf2f7); color: #4a5568; 
     padding: 10px 14px; text-align: left; font-weight: bold; font-size: 10pt; border-bottom: 1px solid #cbd5e0; }
td { padding: 10px 14px; border-bottom: 1px solid #edf2f7; font-size: 10pt; color: #4a5568; }
tr:last-child td { border-bottom: none; }
tr:hover { background: #f7fafc; }

/* 카드 UI 스타일 */
.card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; 
        padding: 16px 20px; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.card-left-accent { border-left: 4px solid #3182ce; } /* 파란 포인트 */
.card-step { background: #f8fbff; border: 1px solid #bee3f8; }

/* 단계별 숫자 디자인 */
.step-num { display: inline-block; background: #3182ce; color: white; border-radius: 50%; 
            width: 24px; height: 24px; text-align: center; line-height: 24px; 
            font-weight: bold; font-size: 10pt; margin-right: 8px; vertical-align: middle; }
.step-title { font-weight: bold; color: #2c5282; font-size: 11pt; vertical-align: middle; }

/* 뱃지(태그) 스타일 */
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; 
       font-size: 9pt; font-weight: bold; margin: 0 2px; vertical-align: middle; }
.tag-work { background: #ebf8ff; color: #2b6cb0; border: 1px solid #bee3f8; } /* 근무 */
.tag-off { background: #fff5f5; color: #c53030; border: 1px solid #fed7d7; }  /* 휴무 */
.tag-auto { background: #f0fff4; color: #2f855a; border: 1px solid #c6f6d5; } /* 자동 */
.tag-info { background: #edf2f7; color: #4a5568; border: 1px solid #e2e8f0; } /* 일반 */

/* 정보/팁 박스 */
.box-tip { background-color: #fffff0; border-left: 4px solid #ecc94b; padding: 12px 16px; margin: 10px 0; color: #744210; }
.box-info { background-color: #ebf8ff; border-left: 4px solid #4299e1; padding: 12px 16px; margin: 10px 0; color: #2b6cb0; }

/* 리스트 */
ul { margin: 8px 0; padding-left: 20px; }
li { margin-bottom: 6px; color: #4a5568; }

/* 구분선 */
hr { border: 0; border-top: 1px solid #e2e8f0; margin: 24px 0; }
</style>
"""

TAB_QUICK_START = _CSS + """
<h2>🚀 빠른 시작 가이드</h2>
<p style="color:#718096; margin-bottom:20px;">NurseScheduler는 복잡한 근무표를 단 4단계로 생성합니다.</p>

<div class="card card-left-accent">
    <div style="margin-bottom:8px;">
        <span class="step-num">1</span><span class="step-title">설정 탭 : 간호사 등록</span>
    </div>
    <div style="margin-left: 36px; color: #4a5568;">
        이름, 역할(비고1), 직급(비고2)을 입력하거나<br>
        <b>[엑셀 불러오기]</b>로 기존 데이터를 한 번에 가져옵니다.
    </div>
</div>

<div class="card card-left-accent">
    <div style="margin-bottom:8px;">
        <span class="step-num">2</span><span class="step-title">요청사항 탭 : 근무/휴무 신청</span>
    </div>
    <div style="margin-left: 36px; color: #4a5568;">
        달력 격자에서 원하는 날짜에 희망 근무나 휴무를 선택합니다.<br>
        신청표 엑셀이 있다면 <b>[신청표 불러오기]</b>로 자동 입력하세요.
    </div>
</div>

<div class="card card-left-accent">
    <div style="margin-bottom:8px;">
        <span class="step-num">3</span><span class="step-title">규칙설정 탭 : 조건 확인</span>
    </div>
    <div style="margin-left: 36px; color: #4a5568;">
        하루 필수 인원, 연속 근무 제한 등 제약 조건을 확인합니다.<br>
        (기본값이 최적화되어 있어 대부분 수정 없이 사용 가능합니다)
    </div>
</div>

<div class="card card-left-accent" style="border-left-color: #805ad5;">
    <div style="margin-bottom:8px;">
        <span class="step-num" style="background:#805ad5;">4</span><span class="step-title" style="color:#553c9a;">결과 탭 : 생성 및 엑셀 저장</span>
    </div>
    <div style="margin-left: 36px; color: #4a5568;">
        <b>[근무표 생성]</b> 버튼을 누르고 1~3분만 기다리세요.<br>
        결과가 나오면 <b>[엑셀 내보내기]</b>로 파일을 저장합니다.
    </div>
</div>

<hr>
<h3>💡 핵심 포인트</h3>
<div class="box-info">
    <b>근무표는 4주(28일) 단위입니다.</b><br>
    시작일은 '설정' 탭 상단에서 지정하며, 솔버는 23개 이상의 복합 제약조건을 고려하여 
    가장 공정하고 효율적인 배치를 찾아냅니다.
</div>
"""

TAB_SETUP = _CSS + """
<h2>⚙️ 설정 탭 안내</h2>

<h3>1. 기본 설정</h3>
<p>상단의 <b>[날짜 선택기]</b>에서 근무표의 시작일을 지정하세요.<br>
선택한 날짜로부터 28일간의 근무표가 생성됩니다.</p>

<h3>2. 간호사 정보 테이블</h3>
<table>
    <tr><th width="20%">컬럼명</th><th>설명</th></tr>
    <tr><td><b>이름</b></td><td>간호사의 이름 (필수)</td></tr>
    <tr><td><b>비고1 (역할)</b></td><td><span class="tag tag-info">책임만</span> <span class="tag tag-info">외상</span> <span class="tag tag-info">격리</span> 등 특수 역할</td></tr>
    <tr><td><b>비고2 (직급)</b></td><td><span class="tag tag-info">책임</span> <span class="tag tag-info">서브차지</span> 또는 빈칸(일반)</td></tr>
    <tr><td><b>특수 옵션</b></td><td>임산부, 남자(생휴 제외), 주4일 근무 등 체크</td></tr>
    <tr><td><b>전월 데이터</b></td><td><b>전월N</b>(야간횟수), <b>수면이월</b>(미사용 수면) 입력</td></tr>
</table>

<h3>3. 스마트 엑셀 불러오기</h3>
<div class="card">
    <b>📂 규칙 엑셀 (근무표_규칙.xlsx)</b><br>
    <span style="color:#718096; font-size:9pt;">간호사 명단과 역할/직급 정보를 한 번에 세팅합니다.</span>
</div>
<div class="card">
    <b>📅 근무 신청표</b><br>
    <span style="color:#718096; font-size:9pt;">간호사별 희망 근무/휴무 신청 내역을 자동으로 읽어옵니다.</span>
</div>
<div class="card" style="border-left: 4px solid #38a169;">
    <b>⏮️ 이전 근무표 (강력 추천)</b><br>
    <span style="color:#718096; font-size:9pt;">
    지난달 근무표를 불러오면 <b>마지막 5일 패턴, N 횟수, 이월 수면</b>을 자동으로 계산하여 
    연속 근무 규칙이 끊기지 않도록 합니다.
    </span>
</div>
"""

TAB_REQUESTS = _CSS + """
<h2>📝 요청사항 탭 안내</h2>

<h3>달력 격자 사용법</h3>
<p>간호사(행)와 날짜(열)가 만나는 셀을 클릭하여 요청사항을 선택합니다.<br>
빈칸으로 두면 <b>솔버가 자동으로 최적의 근무</b>를 배정합니다.</p>

<h3>요청 코드의 의미</h3>
<div class="card">
    <div style="margin-bottom:10px; font-weight:bold; color:#2d3748;">근무 희망 (최대한 반영)</div>
    <span class="tag tag-work">D</span> 주간 근무 희망<br>
    <span class="tag tag-work">E</span> 저녁 근무 희망<br>
    <span class="tag tag-work">N</span> 야간 근무 희망
</div>

<div class="card" style="border-left-color: #e53e3e;">
    <div style="margin-bottom:10px; font-weight:bold; color:#2d3748;">휴무 확정 (반드시 반영)</div>
    <table style="margin:0; border:none;">
        <tr>
            <td style="border:none; padding:4px;"><span class="tag tag-off">OFF</span></td>
            <td style="border:none; padding:4px;">일반 휴무 (보장)</td>
        </tr>
        <tr>
            <td style="border:none; padding:4px;"><span class="tag tag-off">휴가</span></td>
            <td style="border:none; padding:4px;">연차 휴가 (잔여일수 차감)</td>
        </tr>
        <tr>
            <td style="border:none; padding:4px;"><span class="tag tag-off">법휴</span></td>
            <td style="border:none; padding:4px;">법정 공휴일 휴무</td>
        </tr>
        <tr>
            <td style="border:none; padding:4px;"><span class="tag tag-auto">생휴</span></td>
            <td style="border:none; padding:4px;">보건 휴가 (여성 월 1회)</td>
        </tr>
    </table>
</div>

<div class="box-tip">
    💡 <b>Tip:</b> <span class="tag tag-off">D 제외</span> 처럼 <b>'특정 근무 제외'</b> 요청도 가능합니다.<br>
    예를 들어 "이 날은 나이트(N)만 아니면 된다"면 <b>N 제외</b>를 선택하세요.
</div>
"""

TAB_RULES = _CSS + """
<h2>⚖️ 규칙설정 탭 안내</h2>
<p>근무표 생성의 핵심 엔진인 <b>제약 조건</b>을 관리합니다.<br>
기본값은 통상적인 병원 근무 규정에 맞춰져 있습니다.</p>

<h3>필수 인원 설정</h3>
<table>
    <tr><th>근무</th><th>최소 인원</th><th>설명</th></tr>
    <tr>
        <td><span class="tag tag-work">D</span> 주간</td>
        <td><b>7명</b></td>
        <td>평일/주말 동일</td>
    </tr>
    <tr>
        <td><span class="tag tag-work">E</span> 저녁</td>
        <td><b>8명</b></td>
        <td>업무 로딩이 높은 시간대</td>
    </tr>
    <tr>
        <td><span class="tag tag-work">N</span> 야간</td>
        <td><b>7명</b></td>
        <td>야간 당직 인원</td>
    </tr>
</table>

<h3>주요 제약 조건</h3>
<div class="card">
    <b>🛑 근무 연속성 제한</b>
    <ul>
        <li>최대 연속 근무: <b>5일</b> (6일 연속 불가)</li>
        <li>최대 연속 야간(N): <b>3일</b> (4N 불가)</li>
        <li>야간(NN) 후 휴식: 최소 <b>2일 OFF</b> 보장</li>
    </ul>
</div>

<div class="card">
    <b>⚖️ 직급별 밸런스</b>
    <ul>
        <li><b>책임 간호사</b>: 모든 듀티(D/E/N)에 최소 1명 포함</li>
        <li><b>숙련자(책임+서브)</b>: 듀티당 최소 2명 유지</li>
        <li><b>신규/일반</b>: 특정 근무에 쏠리지 않도록 분산</li>
    </ul>
</div>

<div class="box-info">
    <b>역순 근무 금지:</b><br>
    생체 리듬을 위해 <span class="tag tag-work">E</span> → <span class="tag tag-work">D</span> 또는 
    <span class="tag tag-work">N</span> → <span class="tag tag-work">E</span> 와 같은 
    <b>역방향 근무 전환은 엄격히 금지</b>됩니다.
</div>
"""

TAB_RESULT = _CSS + """
<h2>📊 결과 탭 안내</h2>

<h3>1. 근무표 생성</h3>
<p><b>[근무표 생성]</b> 버튼을 누르면 인공지능 솔버가 최적의 해를 탐색합니다.<br>
<span style="color:#718096; font-size:9pt;">(간호사 수와 제약 조건에 따라 10초~3분 소요)</span></p>

<h3>2. 결과 확인 및 수정</h3>
<div class="card">
    <b>상태 표시</b><br>
    <ul>
        <li><span style="color:#e53e3e; font-weight:bold;">빨간 테두리 셀</span>: 요청사항이 반영되지 못한 경우</li>
        <li><b>하단 통계</b>: 날짜별 근무 인원 (부족 시 빨간 배경)</li>
    </ul>
</div>
<p>결과표의 셀을 클릭하여 <b>수동으로 수정</b>할 수 있습니다.<br>
수정 시 16종의 규칙 위반 여부를 즉시 검사하여 경고 메시지를 띄워줍니다.</p>

<h3>3. 공정성 지표</h3>
<table style="width:100%;">
    <tr>
        <td width="33%" align="center" style="background:#f7fafc;"><b>근무 균등성</b></td>
        <td width="33%" align="center" style="background:#f7fafc;"><b>휴무 만족도</b></td>
        <td width="33%" align="center" style="background:#f7fafc;"><b>패턴 건강도</b></td>
    </tr>
</table>
<p style="text-align:center; color:#718096; font-size:9pt;">
    위 3가지 지표를 종합하여 <b>점수(0~100)</b>와 <b>등급(A~F)</b>을 산출합니다.
</p>
"""

TAB_GLOSSARY = _CSS + """
<h2>📚 용어 설명</h2>

<h3>근무 코드</h3>
<table>
    <tr><th width="80">코드</th><th>명칭</th><th>설명</th></tr>
    <tr><td><span class="tag tag-work">D</span></td><td>Day</td><td>주간 근무 (07:00 ~ 15:00)</td></tr>
    <tr><td><span class="tag tag-work">E</span></td><td>Evening</td><td>저녁 근무 (15:00 ~ 23:00)</td></tr>
    <tr><td><span class="tag tag-work">N</span></td><td>Night</td><td>야간 근무 (23:00 ~ 07:00)</td></tr>
    <tr><td><span class="tag tag-work">중2</span></td><td>Middle</td><td>중간조 (10:00 ~ 18:00) *평일만</td></tr>
</table>

<h3>휴무 코드</h3>
<table>
    <tr><th width="80">코드</th><th>명칭</th><th>설명</th></tr>
    <tr><td><span class="tag tag-off">OFF</span></td><td>휴무</td><td>일반 휴무 (주당 1회 이상)</td></tr>
    <tr><td><span class="tag tag-auto">수면</span></td><td>수면오프</td><td>야간 근무 누적에 따른 보상 휴무</td></tr>
    <tr><td><span class="tag tag-auto">POFF</span></td><td>임신부휴</td><td>임신부 연속 근무 후 강제 휴식</td></tr>
    <tr><td><span class="tag tag-off">주</span></td><td>고정주휴</td><td>매주 특정 요일 고정 휴무</td></tr>
</table>

<div class="card" style="border-left-color: #805ad5;">
    <b>🌙 수면(Sleeping Off) 발생 규칙</b><br>
    <div style="margin-top:6px; font-size:9.5pt; color:#4a5568;">
    1. <b>월간 기준:</b> 해당 월 N 근무 7개 이상 → 수면 1개<br>
    2. <b>2개월 합산:</b> (전월N + 당월N) ≥ 11개 → 짝수달에 추가 수면<br>
    * 미사용된 수면은 다음 달 '수면이월'로 넘어갑니다.
    </div>
</div>
"""


# ══════════════════════════════════════════
# 다이얼로그 클래스 (Modern Style)
# ══════════════════════════════════════════

class HelpDialog(QDialog):
    """사용 가이드 다이얼로그"""

    def __init__(self, parent=None, welcome=False):
        super().__init__(parent)
        self._welcome = welcome
        self._init_ui()

    def _init_ui(self):
        title = "NurseScheduler 시작하기" if self._welcome else "사용 가이드"
        self.setWindowTitle(title)
        self.setMinimumSize(850, 650)
        self.resize(900, 700)
        
        # 메인 스타일시트
        self.setStyleSheet("""
            QDialog { background-color: #f8f9fa; }
            
            /* 탭 위젯 스타일 */
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: white;
                top: -1px; 
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background: transparent;
                color: #718096;
                padding: 12px 24px;
                font-family: '맑은 고딕';
                font-size: 10pt;
                font-weight: bold;
                border-bottom: 3px solid transparent;
                margin-right: 2px;
            }
            QTabBar::tab:hover {
                color: #4a5568;
                background: #edf2f7;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                color: #3182ce;
                border-bottom: 3px solid #3182ce;
            }

            /* 버튼 스타일 */
            QPushButton#CloseBtn {
                background-color: #4a5568;
                color: white;
                border: none;
                padding: 10px 30px;
                border-radius: 6px;
                font-family: '맑은 고딕';
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton#CloseBtn:hover { background-color: #2d3748; }
            QPushButton#CloseBtn:pressed { background-color: #1a202c; }

            /* 체크박스 */
            QCheckBox {
                font-family: '맑은 고딕';
                font-size: 10pt;
                color: #4a5568;
                spacing: 8px;
            }
            
            /* 스크롤바 커스텀 */
            QScrollBar:vertical {
                border: none;
                background: #f7fafc;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e0;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover { background: #a0aec0; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 1. 웰컴 배너 (첫 실행 시에만 강조)
        if self._welcome:
            banner = QFrame()
            banner.setStyleSheet("""
                QFrame {
                    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #1a365d, stop:1 #3182ce);
                    border-radius: 12px;
                }
            """)
            banner.setFixedHeight(100)
            
            # 그림자 효과
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setOffset(0, 4)
            shadow.setColor(QColor(0, 0, 0, 40))
            banner.setGraphicsEffect(shadow)

            blayout = QVBoxLayout(banner)
            blayout.setContentsMargins(30, 0, 30, 0)
            blayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            title_lbl = QLabel("Welcome to NurseScheduler")
            title_lbl.setStyleSheet("color: white; font-size: 18pt; font-weight: bold; font-family: '맑은 고딕'; background: transparent;")
            
            sub_lbl = QLabel("효율적인 간호 근무표 관리를 위한 완벽한 솔루션입니다.")
            sub_lbl.setStyleSheet("color: #e2e8f0; font-size: 10pt; font-family: '맑은 고딕'; margin-top: 4px; background: transparent;")

            blayout.addWidget(title_lbl)
            blayout.addWidget(sub_lbl)
            
            layout.addWidget(banner)

        # 2. 메인 탭 위젯
        tabs = QTabWidget()
        tabs.setDocumentMode(True)  # 모던한 느낌을 위해 문서 모드 사용
        
        # 탭 추가 (아이콘을 텍스트에 포함하여 직관성 향상)
        tabs.addTab(_scroll_label(TAB_QUICK_START), "🚀 빠른 시작")
        tabs.addTab(_scroll_label(TAB_SETUP), "⚙️ 설정")
        tabs.addTab(_scroll_label(TAB_REQUESTS), "📝 요청사항")
        tabs.addTab(_scroll_label(TAB_RULES), "⚖️ 규칙설정")
        tabs.addTab(_scroll_label(TAB_RESULT), "📊 결과")
        tabs.addTab(_scroll_label(TAB_GLOSSARY), "📚 용어")
        
        layout.addWidget(tabs)

        # 3. 하단 버튼 영역
        bot_layout = QHBoxLayout()
        bot_layout.setContentsMargins(4, 8, 4, 0)

        if self._welcome:
            self._chk_no_show = QCheckBox("다시는 이 창을 보지 않겠습니다")
            self._chk_no_show.setCursor(Qt.CursorShape.PointingHandCursor)
            bot_layout.addWidget(self._chk_no_show)

        bot_layout.addStretch()

        btn_close = QPushButton("닫기")
        btn_close.setObjectName("CloseBtn")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        bot_layout.addWidget(btn_close)

        layout.addLayout(bot_layout)

    def should_hide_welcome(self) -> bool:
        """'다시 보지 않기' 체크 여부 반환"""
        if self._welcome and hasattr(self, '_chk_no_show'):
            return self._chk_no_show.isChecked()
        return False
