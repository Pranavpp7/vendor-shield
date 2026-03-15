ALTER TABLE public.documents ADD COLUMN source_type text NOT NULL DEFAULT 'file';
ALTER TABLE public.documents ADD COLUMN source_url text;