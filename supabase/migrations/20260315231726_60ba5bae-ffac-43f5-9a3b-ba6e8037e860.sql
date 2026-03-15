
CREATE TABLE public.checklist_schemas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  schema jsonb NOT NULL DEFAULT '[]'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.checklist_schemas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own schema" ON public.checklist_schemas
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own schema" ON public.checklist_schemas
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own schema" ON public.checklist_schemas
  FOR UPDATE TO authenticated USING (auth.uid() = user_id);
