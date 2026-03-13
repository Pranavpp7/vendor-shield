
-- Add embedding column to document_chunks (768 dimensions for Gemini embedding-001)
ALTER TABLE public.document_chunks ADD COLUMN IF NOT EXISTS embedding vector(768);

-- Create index for fast similarity search
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx ON public.document_chunks 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Drop old FTS-based search function
DROP FUNCTION IF EXISTS public.search_document_chunks(text, text, integer);

-- Create vector similarity search function
CREATE OR REPLACE FUNCTION public.search_document_chunks(
  p_assessment_id text, 
  p_query_embedding vector(768),
  p_limit integer DEFAULT 5
)
RETURNS TABLE(
  chunk_id uuid, 
  document_id uuid, 
  file_name text, 
  chunk_index integer, 
  content text, 
  similarity double precision
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    dc.id as chunk_id,
    dc.document_id,
    d.file_name,
    dc.chunk_index,
    dc.content,
    (1 - (dc.embedding <=> p_query_embedding))::double precision as similarity
  FROM public.document_chunks dc
  JOIN public.documents d ON d.id = dc.document_id
  WHERE d.assessment_id = p_assessment_id
    AND d.status = 'ready'
    AND dc.embedding IS NOT NULL
  ORDER BY dc.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$;
