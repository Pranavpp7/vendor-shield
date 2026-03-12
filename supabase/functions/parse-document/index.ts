import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

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

function extractTextFromContent(content: string, contentType: string): string {
  // For plain text files, return as-is
  if (contentType.includes("text/") || contentType.includes("json") || contentType.includes("xml") || contentType.includes("csv")) {
    return content;
  }

  // For PDFs - basic text extraction (strips binary, keeps readable text)
  // This is a simple approach; complex PDFs with only images won't work well
  if (contentType.includes("pdf")) {
    // Extract text between stream/endstream for simple text PDFs
    const textParts: string[] = [];
    
    // Try to find text in PDF streams using BT/ET text blocks
    const btEtRegex = /BT\s*([\s\S]*?)\s*ET/g;
    let match;
    while ((match = btEtRegex.exec(content)) !== null) {
      const block = match[1];
      // Extract text from Tj and TJ operators
      const tjRegex = /\(([^)]*)\)\s*Tj/g;
      let tjMatch;
      while ((tjMatch = tjRegex.exec(block)) !== null) {
        textParts.push(tjMatch[1]);
      }
      // TJ array
      const tjArrayRegex = /\[([^\]]*)\]\s*TJ/g;
      let tjArrMatch;
      while ((tjArrMatch = tjArrayRegex.exec(block)) !== null) {
        const inner = tjArrMatch[1];
        const strings = inner.match(/\(([^)]*)\)/g);
        if (strings) {
          textParts.push(strings.map(s => s.slice(1, -1)).join(""));
        }
      }
    }

    if (textParts.length > 0) {
      return textParts.join(" ").replace(/\\n/g, "\n").replace(/\s+/g, " ").trim();
    }

    // Fallback: extract any readable ASCII sequences
    const readable = content.replace(/[^\x20-\x7E\n\r\t]/g, " ").replace(/\s+/g, " ").trim();
    // Filter out very short meaningless fragments
    const sentences = readable.split(/[.!?]+/).filter(s => s.trim().length > 20);
    return sentences.join(". ").trim();
  }

  // Fallback for other types
  return content.replace(/[^\x20-\x7E\n\r\t]/g, " ").replace(/\s+/g, " ").trim();
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    const { documentId } = await req.json();
    if (!documentId) throw new Error("documentId is required");

    // Get document record
    const { data: doc, error: docErr } = await supabase
      .from("documents")
      .select("*")
      .eq("id", documentId)
      .single();

    if (docErr || !doc) throw new Error("Document not found");

    // Update status to processing
    await supabase.from("documents").update({ status: "processing" }).eq("id", documentId);

    // Download file from storage
    const { data: fileData, error: downloadErr } = await supabase
      .storage
      .from("vendor-documents")
      .download(doc.storage_path);

    if (downloadErr || !fileData) {
      await supabase.from("documents").update({ status: "error" }).eq("id", documentId);
      throw new Error("Failed to download file from storage");
    }

    // Extract text based on content type
    let rawText: string;
    const contentType = doc.content_type || "text/plain";

    if (contentType.includes("text/") || contentType.includes("json") || contentType.includes("csv") || contentType.includes("xml") || contentType.includes("yaml")) {
      rawText = await fileData.text();
    } else {
      // For binary files (PDF etc), read as text and try to extract
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

    // Split into chunks
    const chunks = splitIntoChunks(rawText);

    // Delete existing chunks for this document (in case of re-processing)
    await supabase.from("document_chunks").delete().eq("document_id", documentId);

    // Insert chunks
    const chunkRows = chunks.map((content, i) => ({
      document_id: documentId,
      chunk_index: i,
      content,
    }));

    // Insert in batches of 50
    for (let i = 0; i < chunkRows.length; i += 50) {
      const batch = chunkRows.slice(i, i + 50);
      const { error: insertErr } = await supabase.from("document_chunks").insert(batch);
      if (insertErr) {
        console.error("Chunk insert error:", insertErr);
        await supabase.from("documents").update({ status: "error" }).eq("id", documentId);
        throw new Error("Failed to insert chunks");
      }
    }

    // Mark as ready
    await supabase.from("documents").update({ status: "ready" }).eq("id", documentId);

    return new Response(
      JSON.stringify({ success: true, chunksCreated: chunks.length }),
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
