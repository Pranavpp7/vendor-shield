import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent";

function stripHtml(html: string): string {
  // Remove script, style, nav, footer, header, aside tags and their content
  let text = html.replace(/<(script|style|nav|footer|header|aside|noscript|svg|iframe)[^>]*>[\s\S]*?<\/\1>/gi, " ");
  // Remove all remaining HTML tags
  text = text.replace(/<[^>]+>/g, " ");
  // Decode common HTML entities
  text = text.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ");
  // Normalize whitespace
  text = text.replace(/\s+/g, " ").trim();
  return text;
}

function splitIntoChunks(text: string, chunkSize = 500, overlap = 100): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length <= chunkSize) return [words.join(" ")];

  const chunks: string[] = [];
  let i = 0;
  while (i < words.length) {
    const chunk = words.slice(i, i + chunkSize).join(" ");
    if (chunk.trim()) chunks.push(chunk.trim());
    i += chunkSize - overlap;
  }
  return chunks;
}

async function getEmbedding(text: string, apiKey: string): Promise<number[] | null> {
  try {
    const response = await fetch(`${GEMINI_EMBED_URL}?key=${apiKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "models/gemini-embedding-001",
        content: { parts: [{ text }] },
        taskType: "RETRIEVAL_DOCUMENT",
        outputDimensionality: 768,
      }),
    });

    if (!response.ok) {
      console.error("Embedding API error:", response.status, await response.text());
      return null;
    }

    const data = await response.json();
    return data.embedding?.values ?? null;
  } catch (err) {
    console.error("Embedding fetch error:", err);
    return null;
  }
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const geminiApiKey = Deno.env.get("GEMINI_API_KEY");
    const supabase = createClient(supabaseUrl, supabaseKey);

    const { url, assessmentId, userId } = await req.json();
    if (!url || !assessmentId) throw new Error("url and assessmentId are required");

    // Parse URL for display name
    let displayName: string;
    try {
      const parsed = new URL(url);
      displayName = `${parsed.hostname}${parsed.pathname}`.replace(/\/$/, "");
    } catch {
      displayName = url.slice(0, 100);
    }

    // Create document record
    const { data: doc, error: docErr } = await supabase
      .from("documents")
      .insert({
        assessment_id: assessmentId,
        file_name: displayName,
        file_size: 0,
        content_type: "text/html",
        source_type: "url",
        source_url: url,
        status: "processing",
        user_id: userId || null,
      })
      .select("id")
      .single();

    if (docErr || !doc) throw new Error(`Failed to create document record: ${docErr?.message}`);

    const documentId = doc.id;

    // Fetch URL content
    let rawText: string;
    try {
      const response = await fetch(url, {
        headers: {
          "User-Agent": "Mozilla/5.0 (compatible; VendorShield/1.0)",
          "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
        },
        redirect: "follow",
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const contentType = response.headers.get("content-type") || "";
      const html = await response.text();

      if (contentType.includes("text/plain") || contentType.includes("application/json")) {
        rawText = html;
      } else {
        rawText = stripHtml(html);
      }
    } catch (fetchErr: any) {
      await supabase.from("documents").update({ status: "error" }).eq("id", documentId);
      throw new Error(`Failed to fetch URL: ${fetchErr.message}`);
    }

    if (!rawText || rawText.trim().length < 10) {
      await supabase.from("documents").update({ status: "error" }).eq("id", documentId);
      return new Response(
        JSON.stringify({ error: "Could not extract meaningful text from this URL. The page may require JavaScript rendering." }),
        { status: 422, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Update file_size with extracted text length
    await supabase.from("documents").update({ file_size: rawText.length }).eq("id", documentId);

    const chunks = splitIntoChunks(rawText);

    // Delete existing chunks for this document (in case of re-processing)
    await supabase.from("document_chunks").delete().eq("document_id", documentId);

    // Generate embeddings and insert chunks
    const chunkRows = [];
    for (let i = 0; i < chunks.length; i++) {
      const embedding = geminiApiKey ? await getEmbedding(chunks[i], geminiApiKey) : null;
      chunkRows.push({
        document_id: documentId,
        chunk_index: i,
        content: chunks[i],
        ...(embedding ? { embedding: JSON.stringify(embedding) } : {}),
      });

      if (geminiApiKey && i < chunks.length - 1) {
        await new Promise(r => setTimeout(r, 100));
      }
    }

    // Insert in batches of 20
    for (let i = 0; i < chunkRows.length; i += 20) {
      const batch = chunkRows.slice(i, i + 20);
      const { error: insertErr } = await supabase.from("document_chunks").insert(batch);
      if (insertErr) {
        console.error("Chunk insert error:", insertErr);
        await supabase.from("documents").update({ status: "error" }).eq("id", documentId);
        throw new Error("Failed to insert chunks");
      }
    }

    await supabase.from("documents").update({ status: "ready" }).eq("id", documentId);

    return new Response(
      JSON.stringify({ success: true, documentId, chunksCreated: chunks.length, embeddingsGenerated: !!geminiApiKey }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (e) {
    console.error("parse-url error:", e);
    return new Response(
      JSON.stringify({ error: e instanceof Error ? e.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
