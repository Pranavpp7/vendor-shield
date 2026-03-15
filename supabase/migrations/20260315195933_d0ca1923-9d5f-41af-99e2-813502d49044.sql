CREATE POLICY "Users can delete own document chunks"
ON public.document_chunks
FOR DELETE
TO authenticated
USING (EXISTS (
  SELECT 1 FROM documents d
  WHERE d.id = document_chunks.document_id
  AND d.user_id = auth.uid()
));