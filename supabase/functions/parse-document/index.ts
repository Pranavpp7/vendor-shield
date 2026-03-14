import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";
import { extractText, getDocumentProxy } from "npm:unpdf";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent";

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

    const { documentId } = await req.json();
    if (!documentId) throw new Error("documentId is required");

    const { data: doc, error: docErr } = await supabase
      .from("documents")
      .select("*")
      .eq("id", documentId)
      .single();

    if (docErr || !doc) throw new Error("Document not found");

    await supabase.from("documents").update({ status: "processing" }).eq("id", documentId);

    const { data: fileData, error: downloadErr } = await supabase
      .storage
      .from("vendor-documents")
      .download(doc.storage_path);

    if (downloadErr || !fileData) {
      await supabase.from("documents").update({ status: "error" }).eq("id", documentId);
      throw new Error("Failed to download file from storage");
    }

    let rawText: string;
    const contentType = doc.content_type || "text/plain";

    if (contentType.includes("text/") || contentType.includes("json") || contentType.includes("csv") || contentType.includes("xml") || contentType.includes("yaml")) {
      rawText = await fileData.text();
    } else {
      const arrayBuffer = await fileData.arrayBuffer();
      const decoder = new TextDecoder("utf-8", { fatal: false });
      const rawContent = decoder.decode(arrayBuffer);
      rawText = extractTextFromContent(rawContent, contentType);
    }

    if (!rawText || rawText.trim().length < 10) {
      await supabase.from("documents").update({ status: "error" }).eq("id", documentId);
      return new Response(
        JSON.stringify({ error: "Could not extract meaningful text from this document. Try uploading a text-based file." }),
        { status: 422, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

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

      // Small delay to avoid rate limiting on Gemini free tier
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
      JSON.stringify({ success: true, chunksCreated: chunks.length, embeddingsGenerated: !!geminiApiKey }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (e) {
    console.error("parse-document error:", e);
    return new Response(
      JSON.stringify({ error: e instanceof Error ? e.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
