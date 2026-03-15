CREATE POLICY "Users can delete own runs"
ON public.assessment_runs
FOR DELETE
TO authenticated
USING (auth.uid() = user_id);