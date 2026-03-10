# NurseScheduler — 응급실 간호사 근무표 자동생성

OR-Tools CP-SAT 솔버 기반 제약조건 최적화 + PyQt6 데스크톱 앱

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 자동 근무표 생성 | D/E/N/중2 4종 근무 + 14종 휴무를 월 단위로 자동 배정 |
| 하드 제약조건 | 일일 인원, 역순 금지, 연속근무 제한, 직급/역할 요구 등 23개 |
| 소프트 목적함수 | D/E/N 공정성, 야간 균등, 주말 균등, 요청 반영률 등 5개 |
| 수동 수정 | 생성된 근무표를 셀 단위로 편집 (16종 위반 실시간 체크) |
| 엑셀 연동 | 규칙 엑셀·신청표·이전 근무표 가져오기 / 근무표·통계 내보내기 |
| 공정성 평가 | A~F 등급, 편차·위반 항목별 상세 표시 |
| 자동 백업 | JSON 데이터 `~/Documents/NurseScheduler_backup/` 자동 저장 |

---

## 실행 방법

```bash
# 의존성 설치 (uv 패키지 매니저 사용)
uv sync

# 앱 실행
uv run python main.py

# Windows 독립 실행 파일(.exe) 빌드
build.bat
```

**요구사항**: Python 3.12+ · PyQt6 · ortools · openpyxl

---

## 근무/휴무 코드

| 구분 | 코드 |
|------|------|
| 근무 | `D` (주간) · `E` (저녁) · `N` (야간) · `중2` (중간근무, 평일 전용) |
| 휴무 | `주` · `OFF` · `POFF` · `법휴` · `수면` · `생휴` · `휴가` · `병가` · `특휴` · `공가` · `경가` · `보수` · `필수` · `번표` |
| 요청 제외 | `D 제외` · `E 제외` · `N 제외` |

---

## 사용 흐름

### 1단계 · 설정 탭
간호사 목록을 등록합니다. 이름, 역할(비고1), 직급(비고2), 임산부/남자/주4일제 여부, 고정 주휴, 휴가 잔여일, 전월 N 횟수, 수면 이월 등을 입력합니다.
엑셀 파일(근무표_규칙.xlsx) 또는 이전 근무표에서 한 번에 불러올 수 있습니다.

### 2단계 · 요청사항 탭
간호사별 × 날짜별 콤보박스 격자에서 근무 희망(D/E/N), 휴무 요청(OFF/법휴/휴가 등), 제외 요청(D 제외 등)을 입력합니다.

### 3단계 · 규칙설정 탭
일일 최소 인원, 근무 순서·연속 제한, 직급 조건, 임산부·생리휴무 특칙, 수면휴무 발생 기준(N 횟수 임계값) 등을 설정합니다.

### 4단계 · 결과 탭
**근무표 생성** 버튼 클릭 → 색상 코딩된 결과 확인 → 셀 직접 수정(위반 경고) → **엑셀 내보내기**.
하단에는 근무별 집계, 불량 패턴 감지, 위반 상세, 간호사별 통계(D/E/N 편차·요청 반영률·잔여휴가·잔여수면)가 표시됩니다.

---

## 프로젝트 구조

```
nurse-scheduler/
├── main.py                  ← 실행 진입점
├── engine/                  ← 백엔드 (UI 의존 없음)
│   ├── models.py            ← 데이터 클래스 (Nurse, Request, Rules, Schedule) + JSON 저장/백업
│   ├── solver.py            ← OR-Tools CP-SAT 솔버 (NUM_TYPES=15, 4 workers, 기본 180s timeout)
│   ├── validator.py         ← 수동 수정 시 16종 위반 체크
│   ├── evaluator.py         ← 공정성 평가 (0-100점, A-F 등급)
│   └── excel_io.py          ← 엑셀 가져오기/내보내기
├── ui/                      ← PyQt6 뷰 (탭 1개 = 파일 1개)
│   ├── styles.py            ← SHIFT_COLORS, 앱 스타일시트
│   ├── main_window.py       ← 4탭 메인 윈도우 + 가이드 패널 토글
│   ├── guide_panel.py       ← 탭별 맥락 도움말 사이드 패널
│   ├── setup_tab.py         ← Tab 1: 간호사 관리
│   ├── request_tab.py       ← Tab 2: 요청사항 달력
│   ├── rules_tab.py         ← Tab 3: 규칙 설정
│   └── result_tab.py        ← Tab 4: 결과 표시 + 수동 수정 + 통계
├── assets/icons/            ← 탭 아이콘 (SVG)
├── data/                    ← JSON 저장 파일 (nurses, rules, requests, schedule)
├── build.bat                ← PyInstaller 빌드 스크립트
└── CLAUDE.md                ← Claude Code 개발 가이드
```

---

## 솔버 개요

- **변수**: `shifts[(nurse_idx, day_idx, shift_idx)]` BoolVar — 18종 (D=0 · 중2=1 · E=2 · N=3 · 주=4 · OFF=5 · … · 병가=17)
- **하드 제약**: 역순 근무 금지, 연속 근무/야간 제한, NN 후 2일 오프, 월간 N 상한, 주간 오프, 일일 인원/직급/역할 요구, 임산부·주4일 특칙 등
- **소프트 목적함수**: D/E/N 총량 편차 최소화, 야간 균등, 주말 균등, 요청 반영률 최대화
- **수면 오프**: 2개월 고정 쌍(`(1,2)`, `(3,4)`, …) 기준, 홀수 월 미발생분은 `pending_sleep`으로 이월

---

## 데이터 흐름

```
SetupTab (간호사·연월)
    ↓
RequestTab (요청사항)
    ↓
ResultTab → solver.solve_schedule() → Schedule
    ↓
수동 수정 → validator.validate_change()
    ↓
evaluator.evaluate_schedule() → 공정성 등급/상세
    ↓
excel_io.export_schedule() → .xlsx
```
