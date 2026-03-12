
CREATE OR REPLACE FUNCTION public.search_document_chunks(
  p_assessment_id text,
  p_query text,
  p_limit integer DEFAULT 5
)
RETURNS TABLE (
  chunk_id uuid,
  document_id uuid,
  file_name text,
  chunk_index integer,
  content text,
  rank real
)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  SELECT 
    dc.id as chunk_id,
    dc.document_id,
    d.file_name,
    dc.chunk_index,
    dc.content,
    ts_rank(dc.fts, plainto_tsquery('english', p_query)) as rank
  FROM public.document_chunks dc
  JOIN public.documents d ON d.id = dc.document_id
  WHERE d.assessment_id = p_assessment_id
    AND d.status = 'ready'
    AND dc.fts @@ plainto_tsquery('english', p_query)
  ORDER BY rank DESC
  LIMIT p_limit;
$$;
