
CREATE TABLE public.assessment_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id text NOT NULL,
  user_id uuid NOT NULL,
  score integer NOT NULL DEFAULT 0,
  risk_level text NOT NULL DEFAULT 'Low',
  passed_count integer NOT NULL DEFAULT 0,
  failed_count integer NOT NULL DEFAULT 0,
  needs_info_count integer NOT NULL DEFAULT 0,
  controls jsonb NOT NULL DEFAULT '[]'::jsonb,
  run_at timestamp with time zone NOT NULL DEFAULT now()
);

ALTER TABLE public.assessment_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own runs" ON public.assessment_runs
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own runs" ON public.assessment_runs
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX idx_assessment_runs_assessment_id ON public.assessment_runs(assessment_id);
CREATE INDEX idx_assessment_runs_run_at ON public.assessment_runs(run_at);
