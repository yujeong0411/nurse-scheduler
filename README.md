# NurseScheduler - 응급실 간호사 근무표 자동생성

OR-Tools CP-SAT 솔버 기반 제약조건 최적화 + PyQt6 데스크톱 앱

## 주요 기능

- **자동 근무표 생성**: D/E/N/중2 4종 근무 + 11종 휴무를 28일(4주) 단위로 자동 배정
- **23개 하드 제약조건**: 일일 인원, 역순 금지, 연속근무 제한, 직급/역할 요구 등
- **5개 소프트 목적함수**: D/E/N 공정성, 야간 균등, 주말 균등, 요청 반영
- **수동 수정**: 생성된 근무표를 셀 단위로 편집 (16종 위반 체크)
- **엑셀 가져오기/내보내기**: 규칙 엑셀, 근무신청표, 이전 근무표 가져오기 + 근무표/통계 내보내기
- **공정성 평가**: A~F 등급, 편차/위반 상세 표시

## 실행 방법

```bash
# 의존성 설치 (uv 패키지 매니저)
uv sync

# 실행
uv run python main.py

# Windows exe 빌드
build.bat
```

Python 3.12+ / PyQt6 / ortools / openpyxl

## 프로젝트 구조

```
nurse-scheduler/
├── main.py                  ← 실행 진입점
├── engine/
│   ├── models.py            ← 데이터 클래스 (Nurse, Request, Rules, Schedule) + JSON 저장/백업
│   ├── solver.py            ← OR-Tools CP-SAT 솔버 (15종 변수, 23 하드 + 5 소프트)
│   ├── validator.py         ← 수동 수정 시 16종 위반 체크
│   ├── evaluator.py         ← 공정성 평가 (0-100점, A-F 등급, 위반 상세)
│   └── excel_io.py          ← 엑셀 가져오기/내보내기 (양 형식 날짜 헤더 인식)
├── ui/
│   ├── styles.py            ← 색상, 스타일시트
│   ├── main_window.py       ← 4탭 메인 윈도우
│   ├── setup_tab.py         ← Tab 1: 간호사 관리 (역할/직급/특수조건)
│   ├── request_tab.py       ← Tab 2: 요청사항 달력 (콤보박스 격자)
│   ├── rules_tab.py         ← Tab 3: 규칙 설정 (인원/제한/직급/수면 등)
│   └── result_tab.py        ← Tab 4: 결과 표시 + 수동 수정 + 휴가잔여/잔여수면 + 통계
├── assets/icons/            ← 탭 아이콘 (SVG)
├── data/                    ← JSON 저장 (nurses, rules, requests, schedule)
├── build.bat                ← PyInstaller 빌드 스크립트
├── CLAUDE.md                ← Claude Code 가이드
└── README.md
```

## 근무/휴무 코드

| 구분 | 코드 |
|------|------|
| 근무 | `D` (주간), `E` (저녁), `N` (야간), `중2` (중간, 평일만) |
| 휴무 | `주`, `OFF`, `POFF`, `법휴`, `수면`, `생휴`, `휴가`, `특휴`, `공가`, `경가`, `보수` |
| 요청 | 근무 희망, 휴무 희망, 제외 요청 (`D 제외`, `E 제외`, `N 제외`) |

## 사용 흐름

1. **설정 탭**: 간호사 목록 등록 (규칙 엑셀 / 신청표 엑셀 불러오기 가능)
2. **요청사항 탭**: 개인별 근무 희망/휴무 요청 입력
3. **규칙설정 탭**: 일일 인원, 연속근무 제한, 직급 요구 등 설정
4. **결과 탭**: 근무표 생성 → 확인/수동수정 → 엑셀 내보내기
