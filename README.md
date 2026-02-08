# nurse-scheduler
Automated 3-shift nurse scheduling system with constraint optimization using PyQt6 and OR-Tools

```
nurse-scheduler/
├── main.py                  ← 실행 진입점
├── engine/
│   ├── models.py            ← 데이터 클래스 + JSON 저장/백업
│   ├── solver.py            ← 스케줄링 (테스트용 기본 로직, Day3에 OR-Tools)
│   ├── validator.py         ← 수동 수정 시 7가지 위반 체크
│   ├── evaluator.py         ← 공정성 평가 (스텁)
│   └── excel_io.py          ← 엑셀 내보내기 (스텁)
├── ui/
│   ├── styles.py            ← 색상, 스타일시트
│   ├── main_window.py       ← 4탭 메인 윈도우
│   ├── setup_tab.py         ← 간호사 관리 (테이블 편집)
│   ├── request_tab.py       ← 요청사항 달력 (콤보박스)
│   ├── rules_tab.py         ← 규칙 설정 (체크박스+스핀박스)
│   └── result_tab.py        ← 결과 표시 + 수동 수정 + 통계
├── requirements.txt
├── build.bat                ← .exe 빌드 스크립트
└── README.md
```
