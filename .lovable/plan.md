

# Plan: URL Content Extraction Pipeline

## What We're Building
Enable vendor-provided URLs to be scraped, chunked, embedded, and fed into the existing RAG pipeline — exactly like uploaded documents. Links will appear as document records with status tracking, and work with re-run checklist.

## Steps

### 1. Database Migration
Add two columns to `documents` table:
- `source_type TEXT NOT NULL DEFAULT 'file'` — distinguishes `'file'` vs `'url'`
- `source_url TEXT` — stores the original URL for URL-sourced documents

### 2. New Edge Function: `parse-url`
- Accepts `{ url, assessmentId, userId }`
- Creates a `documents` record with `source_type='url'`, `source_url=<url>`, `file_name=<hostname+path>`
- Fetches page HTML via native `fetch`, strips `<script>`, `<style>`, `<nav>`, `<footer>` tags, removes remaining HTML tags
- Reuses identical chunking (500 words, 100 overlap) and Gemini embedding logic from `parse-document`
- Sets status `pending` → `processing` → `ready`/`error`
- Add to `config.toml` with `verify_jwt = false`

### 3. Update `DocsLinksSection.tsx` — Merge Links into Documents
- When a link is added (and `assessmentId` exists), call `parse-url` edge function instead of just appending to the JSON array
- Links appear in the **Documents** card with a globe icon, URL display, status badge, and timestamp
- Support re-processing (re-fetch URL), deletion (removes document record + chunks)
- Keep the Links card as an input-only area for adding new URLs
- Already-processed URLs show in the documents list, filtered by `source_type='url'`

### 4. Update `NewAssessment.tsx` — Creation Flow
- After file uploads, submit each link to `parse-url`
- Include URL documents in `waitForDocumentsReady` polling

### 5. No Changes Needed
- `vendor-ai` and `search_document_chunks` already query by `assessment_id` — URL-sourced chunks are automatically included
- Cleanup edge function already deletes all documents for an assessment

## File Changes Summary
| File | Action |
|------|--------|
| `documents` table | Migration: add `source_type`, `source_url` columns |
| `supabase/functions/parse-url/index.ts` | New edge function |
| `supabase/config.toml` | Add `parse-url` entry |
| `src/components/assessment/DocsLinksSection.tsx` | Integrate URL submission + show URL docs in list |
| `src/pages/NewAssessment.tsx` | Submit links to `parse-url` during creation |

