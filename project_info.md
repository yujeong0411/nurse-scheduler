# NurseScheduler 웹 전환 프로젝트

## 프로젝트 개요
PyQt6로 만든 간호사 근무표 자동생성 프로그램을 웹앱으로 전환하는 작업이다.
간호사들이 모바일로 근무 신청을 하고, 수간호사(관리자)가 PC에서 근무표를 생성한다.

---

## 절대 수정 금지 파일 (engine/)
아래 파일들은 어떤 상황에서도 수정하지 않는다.
- `engine/solver.py` — OR-Tools CP-SAT 솔버 (핵심 로직)
- `engine/models.py` — 데이터 모델
- `engine/excel_io.py` — 엑셀 입출력
- `engine/validator.py` — 유효성 검사
- `engine/kr_holidays.py` — 한국 공휴일
- `engine/evaluator.py` — 근무표 평가

---

## 기술 스택
- **백엔드**: FastAPI + Python (engine/ 재사용)
- **프론트엔드**: React + TypeScript + Vite + TailwindCSS
- **DB**: Supabase (PostgreSQL)
- **배포**: Render(백엔드 무료) + Vercel(프론트 무료)
- **인증**: PIN 방식 (JWT 없음, 단순하게)

---

## 폴더 구조
```
nurse-scheduler/
├── engine/                  ← 수정 금지
├── backend/                 ← FastAPI
│   ├── main.py
│   ├── db.py
│   ├── schemas.py
│   ├── deps.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── settings.py
│   │   ├── nurses.py
│   │   ├── pins.py
│   │   ├── requests.py
│   │   └── schedule.py
│   ├── requirements.txt
│   └── render.yaml
└── frontend/                ← React
    └── src/
        ├── App.tsx
        ├── api/client.ts
        ├── constants/shifts.ts
        ├── pages/
        │   ├── LandingPage.tsx
        │   ├── nurse/
        │   │   ├── NurseAuth.tsx
        │   │   └── NursePage.tsx
        │   └── admin/
        │       ├── AdminAuth.tsx
        │       └── AdminPage.tsx
        └── components/
            ├── ShiftSheet.tsx
            ├── ShiftBadge.tsx
            └── admin/
                ├── SettingsTab.tsx
                ├── NurseManagement.tsx
                ├── PinManagement.tsx
                ├── SubmissionsTab.tsx
                └── ScheduleTab.tsx
```

---

## DB 스키마 (Supabase)

### departments (부서)
```sql
id            UUID PK
name          TEXT NOT NULL
admin_pw_hash TEXT NOT NULL  -- bcrypt (초기: "1234")
```

### nurses (간호사)
```sql
id               UUID PK
department_id    UUID FK → departments
name             TEXT NOT NULL
role             TEXT
grade            TEXT
is_pregnant      BOOL
is_male          BOOL
is_4day_week     BOOL
fixed_weekly_off INT   -- 0=월~6=일
vacation_days    INT
prev_month_n     INT
pending_sleep    BOOL
menstrual_used   BOOL
prev_tail_shifts JSONB
note             TEXT
pin_hash         TEXT  -- bcrypt (초기: "0000")
sort_order       INT
created_at       TIMESTAMPTZ
```

### rules (근무 규칙, 부서당 1행)
```sql
id                     UUID PK
department_id          UUID FK → departments UNIQUE
daily_d                INT default 7
daily_e                INT default 8
daily_n                INT default 7
daily_m                INT default 1
max_n_per_month        INT default 6
max_consecutive_n      INT default 3
off_after_2n           INT default 2
max_consecutive_work   INT default 5
min_weekly_off         INT default 2
ban_reverse_order      BOOL default true
min_chief_per_shift    INT default 1
min_senior_per_shift   INT default 2
pregnant_poff_interval INT default 4
menstrual_leave        BOOL default true
sleep_n_monthly        INT default 7
sleep_n_bimonthly      INT default 11
public_holidays        JSONB default '[]'
```

### periods (근무 기간, 28일 주기)
```sql
id            UUID PK
department_id UUID FK → departments
start_date    DATE NOT NULL
deadline      DATE
UNIQUE(department_id, start_date)
```

### requests (근무 신청)
```sql
id           UUID PK
period_id    UUID FK → periods
nurse_id     UUID FK → nurses
day          INT (1~28)
code         TEXT
is_or        BOOL
submitted_at TIMESTAMPTZ
UNIQUE(period_id, nurse_id, day, code)
```

### solver_jobs (솔버 작업 상태)
```sql
id          UUID PK
period_id   UUID FK → periods
status      TEXT  -- pending | running | done | failed
schedule_id UUID
started_at  TIMESTAMPTZ
finished_at TIMESTAMPTZ
error_msg   TEXT
```

### schedules (생성된 근무표)
```sql
id            UUID PK
period_id     UUID FK → periods
job_id        UUID FK → solver_jobs
schedule_data JSONB  -- {"nurse_uuid": {"1": "D", "2": "N", ...}}
score         INT
grade         TEXT
eval_details  JSONB
created_at    TIMESTAMPTZ
```

---

## API 엔드포인트

### 인증
```
POST  /api/auth/admin          관리자 로그인
POST  /api/auth/nurse          간호사 PIN 로그인
PUT   /api/auth/admin-pw       관리자 비밀번호 변경
PUT   /api/auth/pin/{nurse_id} PIN 변경
```

### 설정
```
GET   /api/settings            시작일·마감일·규칙 조회
PUT   /api/settings            저장
```

### 간호사
```
GET    /api/nurses
POST   /api/nurses
PUT    /api/nurses/{id}
DELETE /api/nurses/{id}
POST   /api/nurses/import-excel
```

### 근무신청
```
GET  /api/requests?period=         전체 현황 (관리자)
GET  /api/requests/me?period=      본인 신청 (간호사)
PUT  /api/requests                 신청 upsert
GET  /api/requests/export?period=  xlsx 다운로드
```

### 근무표
```
POST /api/schedule/generate           솔버 실행 → job_id 반환
GET  /api/schedule/status/{job_id}    폴링
GET  /api/schedule?period=            결과 조회
PUT  /api/schedule/cell               셀 수정
GET  /api/schedule/evaluate?period=   평가
GET  /api/schedule/export?period=     xlsx 다운로드
```

### 기타
```
GET  /api/health               서버 상태 (워밍업용)
GET  /api/holidays?year=&month= 공휴일 조회
```

---

## 솔버 비동기 흐름
```
POST /api/schedule/generate
  → BackgroundTask로 solver 실행 (최대 180초)
  → solver_jobs.status = 'generating'
  → job_id 즉시 반환

프론트: 3초마다 GET /api/schedule/status/{job_id} 폴링
  → generating: 진행바 표시
  → done: 결과 그리드 로드
  → failed: 오류 메시지 + 재시도 버튼
```

---

## 관리자 탭 구성
1. ⚙️ 설정 — 시작일·마감일·규칙
2. 👥 간호사 — 명단 CRUD
3. 🔐 PIN — PIN 초기화
4. 📋 신청현황 — 제출 현황·엑셀 다운로드
5. 📊 근무표 생성 — 솔버 실행·결과 편집·내보내기

---

## 작업 단계 (Phase)

### ✅ Phase 1 — 백엔드 기반
- FastAPI 프로젝트 세팅 + uv
- Supabase 테이블 생성 (DDL)
- db.py: supabase-py 클라이언트
- schemas.py: Pydantic 모델
- auth.py: PIN bcrypt 인증 -> 현재 jwt인데 고민 중

### 🔄 Phase 2 — 핵심 API
- settings.py: 시작일·마감일·규칙 조회·저장
- nurses.py: CRUD + 엑셀 임포트
- requests.py: 신청 upsert·조회·엑셀 export
- pins.py: PIN 변경·초기화

### Phase 3 — 프론트엔드 기반
- Vite + React + TypeScript + TailwindCSS 세팅
- api/client.ts: axios 인스턴스
- constants/shifts.ts: 근무코드 상수
- App.tsx: 라우팅

### Phase 4 — 간호사 UI
- LandingPage.tsx
- NurseAuth.tsx: 이름 선택 + PIN 입력
- NursePage.tsx: 신청 달력 + 제출
- ShiftSheet.tsx: 바텀시트 선택기

### Phase 5 — 관리자 UI
- AdminAuth.tsx + AdminPage.tsx
- SettingsTab, NurseManagement, PinManagement, SubmissionsTab
- ScheduleTab.tsx (신규): 생성·편집·내보내기

### Phase 6 — 배포
- Render: backend/ 배포, 환경변수 설정
- Vercel: frontend/ 배포
- Supabase RLS 정책 설정

---

## 무료 티어 제약 대응
| 서비스 | 제약 | 대응 |
|--------|------|------|
| Render | 15분 비활성 → 슬립 | Landing 진입 시 /api/health 워밍업 |
| Render | RAM 512MB | 간호사 50명 이내 권장 |
| Supabase | 500MB DB | 오래된 period 정기 삭제 |
| Supabase | 7일 비활성 정지 | 7일마다 1회 이상 접속 필요 |
| Vercel | 정적 배포만 | React 빌드 결과물만 올림 (문제없음) |

---

## 환경변수 (backend/.env)
```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SECRET_KEY=
ADMIN_DEPARTMENT_ID=
```