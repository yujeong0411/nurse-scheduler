-- ══════════════════════════════════════════
-- NurseScheduler Supabase Schema
-- Supabase Dashboard → SQL Editor에서 실행
-- ══════════════════════════════════════════

-- 부서 (ER, ICU, 병동 등 / 관리자 비밀번호 포함)
CREATE TABLE departments (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    admin_pw_hash TEXT NOT NULL   -- bcrypt 해시 (초기: hash("1234"))
);

-- 간호사
CREATE TABLE nurses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id    UUID REFERENCES departments(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    role             TEXT DEFAULT '',
    grade            TEXT DEFAULT '',
    is_pregnant      BOOLEAN DEFAULT FALSE,
    is_male          BOOLEAN DEFAULT FALSE,
    is_4day_week     BOOLEAN DEFAULT FALSE,
    fixed_weekly_off INT,          -- 0=월 ~ 6=일, NULL=미지정
    vacation_days    INT DEFAULT 0,
    prev_month_n     INT DEFAULT 0,
    pending_sleep    BOOLEAN DEFAULT FALSE,
    menstrual_used   BOOLEAN DEFAULT FALSE,
    prev_tail_shifts JSONB DEFAULT '[]',
    note             TEXT DEFAULT '',
    pin_hash         TEXT NOT NULL DEFAULT '',  -- bcrypt 해시 (초기: hash("0000"))
    sort_order       INT DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 근무 규칙 (부서당 1행)
CREATE TABLE rules (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id          UUID REFERENCES departments(id) ON DELETE CASCADE UNIQUE,
    daily_d                INT DEFAULT 7,
    daily_e                INT DEFAULT 8,
    daily_n                INT DEFAULT 7,
    daily_m                INT DEFAULT 1,
    max_n_per_month        INT DEFAULT 6,
    max_consecutive_n      INT DEFAULT 3,
    off_after_2n           INT DEFAULT 2,
    max_consecutive_work   INT DEFAULT 5,
    min_weekly_off         INT DEFAULT 2,
    ban_reverse_order      BOOLEAN DEFAULT TRUE,
    min_chief_per_shift    INT DEFAULT 1,
    min_senior_per_shift   INT DEFAULT 2,
    pregnant_poff_interval INT DEFAULT 4,
    menstrual_leave        BOOLEAN DEFAULT TRUE,
    sleep_n_monthly        INT DEFAULT 7,
    sleep_n_bimonthly      INT DEFAULT 11,
    public_holidays        JSONB DEFAULT '[]',
    updated_at             TIMESTAMPTZ DEFAULT NOW()
);

-- 근무 기간 (start_date 기준 28일 주기)
CREATE TABLE periods (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id UUID REFERENCES departments(id) ON DELETE CASCADE,
    start_date    DATE NOT NULL,
    deadline      TEXT,          -- "YYYY-MM-DDTHH:MM" 또는 "YYYY-MM-DD" 형식
    is_active     BOOLEAN DEFAULT FALSE,  -- 간호사에게 표시할 기간
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(department_id, start_date)
);

-- 근무 신청
CREATE TABLE requests (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_id    UUID REFERENCES periods(id) ON DELETE CASCADE,
    nurse_id     UUID REFERENCES nurses(id) ON DELETE CASCADE,
    day          INT NOT NULL CHECK (day BETWEEN 1 AND 28),
    code         TEXT NOT NULL,
    is_or        BOOLEAN DEFAULT FALSE,
    note         TEXT DEFAULT '',
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(period_id, nurse_id, day, code)
);

-- 솔버 작업 상태 추적
CREATE TABLE solver_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_id   UUID REFERENCES periods(id) ON DELETE CASCADE,
    status      TEXT DEFAULT 'pending'
                  CHECK (status IN ('pending', 'running', 'done', 'failed')),
    schedule_id UUID,   -- done 시 채워짐 (self-ref는 아래 FK로)
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_msg   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 생성된 근무표
CREATE TABLE schedules (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_id     UUID REFERENCES periods(id) ON DELETE CASCADE,
    job_id        UUID REFERENCES solver_jobs(id),
    schedule_data JSONB NOT NULL DEFAULT '{}',
    -- {"nurse_uuid": {"1": "D", "2": "N", ...}}
    score         INT,
    grade         TEXT,
    eval_details  JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- solver_jobs.schedule_id FK (schedules 생성 후 추가)
ALTER TABLE solver_jobs
  ADD CONSTRAINT fk_solver_jobs_schedule
  FOREIGN KEY (schedule_id) REFERENCES schedules(id);

-- ── 인덱스 ──────────────────────────────────────
CREATE INDEX idx_nurses_dept       ON nurses(department_id, sort_order);
CREATE INDEX idx_requests_period   ON requests(period_id);
CREATE INDEX idx_requests_nurse    ON requests(nurse_id);
CREATE INDEX idx_schedules_period  ON schedules(period_id);
CREATE INDEX idx_solver_jobs_status ON solver_jobs(status);
CREATE INDEX idx_periods_dept      ON periods(department_id, start_date DESC);

-- ── Row Level Security ───────────────────────────
-- 백엔드는 service_role key 사용 → RLS 우회
-- ALTER TABLE nurses ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE requests ENABLE ROW LEVEL SECURITY;


-- ══════════════════════════════════════════
-- 초기 데이터 삽입 (부서 1개)
-- admin_pw_hash: bcrypt("1234") 값을 Python에서 생성 후 교체
-- ══════════════════════════════════════════
-- INSERT INTO departments (name, admin_pw_hash)
-- VALUES ('응급실', '$2b$12$<bcrypt_hash_here>');
