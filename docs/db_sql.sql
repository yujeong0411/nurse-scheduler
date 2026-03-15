-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.
CREATE TABLE public.departments (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  admin_pw_hash text NOT NULL,
  CONSTRAINT departments_pkey PRIMARY KEY (id)
);
CREATE TABLE public.nurses (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  department_id uuid,
  name text NOT NULL,
  role text DEFAULT ''::text,
  grade text DEFAULT ''::text,
  is_pregnant boolean DEFAULT false,
  is_male boolean DEFAULT false,
  is_4day_week boolean DEFAULT false,
  fixed_weekly_off integer,
  vacation_days integer DEFAULT 0,
  prev_month_n integer DEFAULT 0,
  pending_sleep boolean DEFAULT false,
  menstrual_used boolean DEFAULT false,
  prev_tail_shifts jsonb DEFAULT '[]'::jsonb,
  note text DEFAULT ''::text,
  pin_hash text NOT NULL DEFAULT ''::text,
  sort_order integer DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT nurses_pkey PRIMARY KEY (id),
  CONSTRAINT nurses_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id)
);
CREATE TABLE public.periods (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  department_id uuid,
  start_date date NOT NULL,
  deadline text,
  created_at timestamp with time zone DEFAULT now(),
  is_active boolean DEFAULT false,
  CONSTRAINT periods_pkey PRIMARY KEY (id),
  CONSTRAINT periods_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id)
);
CREATE TABLE public.requests (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  period_id uuid,
  nurse_id uuid,
  day integer NOT NULL CHECK (
    day >= 1
    AND day <= 28
  ),
  code text NOT NULL,
  is_or boolean DEFAULT false,
  submitted_at timestamp with time zone DEFAULT now(),
  note text DEFAULT ''::text,
  CONSTRAINT requests_pkey PRIMARY KEY (id),
  CONSTRAINT requests_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.periods(id),
  CONSTRAINT requests_nurse_id_fkey FOREIGN KEY (nurse_id) REFERENCES public.nurses(id)
);
CREATE TABLE public.rules (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  department_id uuid UNIQUE,
  daily_d integer DEFAULT 7,
  daily_e integer DEFAULT 8,
  daily_n integer DEFAULT 7,
  daily_m integer DEFAULT 1,
  max_n_per_month integer DEFAULT 6,
  max_consecutive_n integer DEFAULT 3,
  off_after_2n integer DEFAULT 2,
  max_consecutive_work integer DEFAULT 5,
  min_weekly_off integer DEFAULT 2,
  ban_reverse_order boolean DEFAULT true,
  min_chief_per_shift integer DEFAULT 1,
  min_senior_per_shift integer DEFAULT 2,
  pregnant_poff_interval integer DEFAULT 4,
  menstrual_leave boolean DEFAULT true,
  sleep_n_monthly integer DEFAULT 7,
  sleep_n_bimonthly integer DEFAULT 11,
  public_holidays jsonb DEFAULT '[]'::jsonb,
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT rules_pkey PRIMARY KEY (id),
  CONSTRAINT rules_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id)
);
CREATE TABLE public.schedules (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  period_id uuid,
  job_id uuid,
  schedule_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  score integer,
  grade text,
  eval_details jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT schedules_pkey PRIMARY KEY (id),
  CONSTRAINT schedules_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.periods(id),
  CONSTRAINT schedules_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.solver_jobs(id)
);
CREATE TABLE public.solver_jobs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  period_id uuid,
  status text DEFAULT 'pending'::text CHECK (
    status = ANY (
      ARRAY ['pending'::text, 'running'::text, 'done'::text, 'failed'::text]
    )
  ),
  schedule_id uuid,
  started_at timestamp with time zone,
  finished_at timestamp with time zone,
  error_msg text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT solver_jobs_pkey PRIMARY KEY (id),
  CONSTRAINT solver_jobs_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.periods(id),
  CONSTRAINT fk_solver_jobs_schedule FOREIGN KEY (schedule_id) REFERENCES public.schedules(id)
);