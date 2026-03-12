
-- Document metadata
CREATE TABLE public.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id text NOT NULL,
  file_name text NOT NULL,
  file_size integer DEFAULT 0,
  content_type text DEFAULT 'application/octet-stream',
  storage_path text,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'ready', 'error')),
  created_at timestamptz DEFAULT now()
);

-- Document chunks with FTS
CREATE TABLE public.document_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid REFERENCES public.documents(id) ON DELETE CASCADE NOT NULL,
  chunk_index integer NOT NULL,
  content text NOT NULL,
  fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE INDEX idx_chunks_fts ON public.document_chunks USING GIN (fts);
CREATE INDEX idx_chunks_document_id ON public.document_chunks (document_id);
CREATE INDEX idx_documents_assessment_id ON public.documents (assessment_id);

-- Storage bucket for vendor documents
INSERT INTO storage.buckets (id, name, public) VALUES ('vendor-documents', 'vendor-documents', true);

-- RLS - public access for now (no auth)
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to documents" ON public.documents FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access to document_chunks" ON public.document_chunks FOR ALL USING (true) WITH CHECK (true);

-- Storage policies
CREATE POLICY "Allow public upload" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'vendor-documents');
CREATE POLICY "Allow public read" ON storage.objects FOR SELECT USING (bucket_id = 'vendor-documents');
CREATE POLICY "Allow public delete" ON storage.objects FOR DELETE USING (bucket_id = 'vendor-documents');

-- FTS search function
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
