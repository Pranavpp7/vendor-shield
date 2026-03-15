-- Create assessments table
CREATE TABLE public.assessments (
  id text PRIMARY KEY,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  vendor_name text NOT NULL,
  criticality text NOT NULL DEFAULT 'Medium',
  created_at text NOT NULL,
  status text NOT NULL DEFAULT 'Draft',
  score integer NOT NULL DEFAULT 0,
  risk_level text NOT NULL DEFAULT 'Low',
  controls jsonb NOT NULL DEFAULT '[]'::jsonb,
  notes text NOT NULL DEFAULT '',
  chat_history jsonb NOT NULL DEFAULT '[]'::jsonb,
  uploaded_files jsonb NOT NULL DEFAULT '[]'::jsonb,
  links jsonb NOT NULL DEFAULT '[]'::jsonb,
  updated_at timestamptz DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.assessments ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "Users can view own assessments"
  ON public.assessments FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own assessments"
  ON public.assessments FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own assessments"
  ON public.assessments FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own assessments"
  ON public.assessments FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);