import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const AI_GATEWAY = "https://ai.gateway.lovable.dev/v1/chat/completions";
const GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent";

async function getQueryEmbedding(text: string, apiKey: string): Promise<number[] | null> {
  try {
    const response = await fetch(`${GEMINI_EMBED_URL}?key=${apiKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "models/gemini-embedding-001",
        content: { parts: [{ text }] },
        taskType: "RETRIEVAL_QUERY",
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

async function retrieveRAGContext(
  supabase: any,
  assessmentId: string,
  searchQuery: string,
  geminiApiKey: string | undefined
): Promise<string> {
  try {
    const embedding = geminiApiKey ? await getQueryEmbedding(searchQuery, geminiApiKey) : null;

    if (embedding) {
      const { data: chunks } = await supabase.rpc("search_document_chunks", {
        p_assessment_id: assessmentId,
        p_query_embedding: JSON.stringify(embedding),
        p_limit: 8,
      });

      if (chunks && chunks.length > 0) {
        return "\n\n--- RETRIEVED DOCUMENT CONTEXT ---\n" +
          chunks.map((c: any) => `[Source: ${c.file_name}, Section ${c.chunk_index + 1}, Relevance: ${(c.similarity * 100).toFixed(0)}%]:\n${c.content}`).join("\n\n") +
          "\n--- END DOCUMENT CONTEXT ---\n";
      }
    }
  } catch (ragErr) {
    console.error("RAG retrieval error (non-fatal):", ragErr);
  }
  return "";
}

async function retrievePerControlRAG(
  supabase: any,
  assessmentId: string,
  controlName: string,
  geminiApiKey: string | undefined
): Promise<string> {
  try {
    const embedding = geminiApiKey ? await getQueryEmbedding(controlName, geminiApiKey) : null;
    if (embedding) {
      const { data: chunks } = await supabase.rpc("search_document_chunks", {
        p_assessment_id: assessmentId,
        p_query_embedding: JSON.stringify(embedding),
        p_limit: 24,
      });

      if (chunks && chunks.length > 0) {
        const uniqueDocChunks = new Map<string, any>();
        for (const chunk of chunks) {
          if (!uniqueDocChunks.has(chunk.file_name)) {
            uniqueDocChunks.set(chunk.file_name, chunk);
          }
          if (uniqueDocChunks.size >= 8) break;
        }

        return Array.from(uniqueDocChunks.values())
          .map((c: any) => `[${c.file_name}, Section ${c.chunk_index + 1}, ${(c.similarity * 100).toFixed(0)}% match]: ${c.content}`)
          .join("\n");
      }
    }
  } catch (err) {
    console.error("Per-control RAG error:", err);
  }
  return "";
}

async function hasIndexedDocuments(supabase: any, assessmentId: string): Promise<boolean> {
  const { data } = await supabase
    .from("documents")
    .select("id")
    .eq("assessment_id", assessmentId)
    .eq("status", "ready")
    .limit(1);
  return data && data.length > 0;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY is not configured");

    const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY");

    const { action, ...params } = await req.json();
    let messages: { role: string; content: string }[];
    let maxTokens = 800;

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // RAG context for chat / summary
    let ragContext = "";
    if (params.assessmentId && (action === "chat" || action === "generate-summary")) {
      const searchQuery = action === "chat"
        ? params.question
        : params.vendorName + " risk assessment summary";
      ragContext = await retrieveRAGContext(supabase, params.assessmentId, searchQuery, GEMINI_API_KEY);
    }

    if (action === "generate-checklist") {
      // Check if we have indexed documents for evidence-based evaluation
      const hasDocs = params.assessmentId ? await hasIndexedDocuments(supabase, params.assessmentId) : false;

      let controlEvidenceMap = "";
      if (hasDocs && params.assessmentId && GEMINI_API_KEY) {
        // Retrieve per-control evidence
        const evidenceEntries: string[] = [];
        for (const c of params.controls) {
          const evidence = await retrievePerControlRAG(supabase, params.assessmentId, c.name, GEMINI_API_KEY);
          evidenceEntries.push(`### ${c.id}: ${c.name}\n${evidence || "NO EVIDENCE FOUND IN DOCUMENTS"}`);
        }
        controlEvidenceMap = "\n\n--- PER-CONTROL DOCUMENT EVIDENCE ---\n" + evidenceEntries.join("\n\n") + "\n--- END PER-CONTROL EVIDENCE ---\n";
      }

      const controlNames = params.controls
        .map((c: { id: string; name: string }) => `${c.id}: ${c.name}`)
        .join("\n");

      const systemPrompt = hasDocs
        ? `You are a rigorous vendor security assessor for a bank. You MUST evaluate each control STRICTLY based on the document evidence provided. 
RULES:
- A control is "passed" ONLY if you find clear, specific evidence in the documents that the control requirement is met.
- A control is "failed" ONLY if documents explicitly show non-compliance or contradictory evidence (e.g., a policy that explicitly states MFA is not required).
- A control is "needs_info" if no relevant evidence exists in the documents, OR if documents partially address the control but lack sufficient detail to confirm compliance. When in doubt, use "needs_info" rather than "failed".
- In the aiExplanation field, cite the SPECIFIC document name and what evidence you found (or didn't find).
- In the evidenceSource field, put the exact document file name where evidence was found, or "No evidence found" if none.
- Do NOT assume compliance without evidence. But also do NOT mark as "failed" just because evidence is missing — that should be "needs_info".
Always respond with valid JSON only, no markdown code blocks.` + controlEvidenceMap
        : `You are generating a preliminary vendor security checklist assessment. No documents have been uploaded yet, so mark most controls as "needs_info" since there is no evidence to evaluate.
RULES:
- Without documents, most controls should be "needs_info" status.
- Only mark obviously publicly verifiable items (like well-known certifications or publicly documented product features) as "passed" if the vendor is well-known AND you can cite a specific public source.
- When marking a control as "passed" based on public knowledge, you MUST set evidenceSource to a real, valid public URL where this information can be verified (e.g., the vendor's official documentation page, trust/security page, or compliance page). For example: "https://www.darwinbox.com/security" or "https://trust.servicenow.com".
- When a control is "needs_info", set evidenceSource to "No documents uploaded".
- In the aiExplanation, clearly state this is based on publicly available information and cite the source.
Always respond with valid JSON only, no markdown code blocks.`;

      messages = [
        { role: "system", content: systemPrompt },
        {
          role: "user",
          content: `Evaluate vendor "${params.vendorName}" against these security controls:\n${controlNames}\n\nReturn JSON: { "results": [{ "id": "<control_id>", "status": "passed"|"failed"|"needs_info", "comment": "short comment", "aiExplanation": "2-3 sentence explanation citing specific document evidence or lack thereof", "evidenceSource": "exact document filename or No evidence found" }], "score": <0-100>, "riskLevel": "Low"|"Medium"|"High" }\n\nScore must reflect actual evidence-based pass rate. Ensure valid JSON.`,
        },
      ];
      maxTokens = 4000;
    } else if (action === "chat") {
      messages = [
        {
          role: "system",
          content:
            "You are a security assessment assistant for Bank ABC. Provide clear, professional analysis based on the vendor assessment data. Keep responses concise and actionable. Use bullet points where appropriate." +
            (ragContext ? "\n\nUse the following uploaded document evidence to provide grounded, evidence-based answers. Always cite the source document name when referencing information from documents." + ragContext : ""),
        },
        {
          role: "user",
          content: `Assessment context:\n${params.context}\n\nQuestion: ${params.question}`,
        },
      ];
    } else if (action === "generate-summary") {
      messages = [
        {
          role: "system",
          content:
            "You are a security assessment report writer for Bank ABC. Generate a concise executive summary of the vendor risk assessment. Use markdown formatting with headers and bullet points." +
            (ragContext ? "\n\nIncorporate evidence from the following uploaded documents to support your findings." + ragContext : ""),
        },
        {
          role: "user",
          content: `Generate a risk posture summary for vendor "${params.vendorName}".\nScore: ${params.score}/100\nRisk Level: ${params.riskLevel}\nControls: ${JSON.stringify(params.controls)}\nAnalyst notes: ${params.notes || "None"}\n\nInclude: executive overview, key findings, failed controls, recommendations.`,
        },
      ];
      maxTokens = 1000;
    } else {
      return new Response(
        JSON.stringify({ error: "Unknown action" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const response = await fetch(AI_GATEWAY, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages,
        max_tokens: maxTokens,
        temperature: action === "generate-checklist" ? 0.3 : 0.7,
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(
          JSON.stringify({ error: "Rate limit exceeded. Please try again shortly." }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (response.status === 402) {
        return new Response(
          JSON.stringify({ error: "AI credits exhausted. Please add credits in workspace settings." }),
          { status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      const errorText = await response.text();
      console.error("AI gateway error:", response.status, errorText);
      throw new Error(`AI gateway error: ${response.status}`);
    }

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;

    if (action === "generate-checklist") {
      try {
        const cleanContent = content.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
        const parsed = JSON.parse(cleanContent);
        const controls = params.controls.map((c: { id: string; category: string; name: string }) => {
          const result = parsed.results?.find((r: { id: string }) => r.id === c.id);
          const status = result?.status || "needs_info";
          return {
            ...c,
            passed: status === "passed",
            status,
            comment: result?.comment ?? "",
            aiExplanation: result?.aiExplanation ?? "No AI analysis available for this control.",
            evidenceSource: result?.evidenceSource ?? "No evidence found",
          };
        });
        return new Response(
          JSON.stringify({
            controls,
            score: parsed.score ?? 0,
            riskLevel: parsed.riskLevel ?? "High",
          }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      } catch (parseErr) {
        console.error("JSON parse error:", parseErr, "Content:", content);
        // Fallback: all needs_info when we can't parse
        const controls = params.controls.map((c: { id: string; category: string; name: string }) => ({
          ...c,
          passed: false,
          status: "needs_info",
          comment: "Unable to evaluate - AI response parsing failed",
          aiExplanation: "The AI assessment could not be parsed. Please re-run the checklist.",
          evidenceSource: "Parse error",
        }));
        return new Response(
          JSON.stringify({
            controls,
            score: 0,
            riskLevel: "High",
          }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    } else if (action === "chat") {
      return new Response(
        JSON.stringify({ reply: content }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    } else {
      return new Response(
        JSON.stringify({ summary: content }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }
  } catch (e) {
    console.error("Edge function error:", e);
    return new Response(
      JSON.stringify({ error: e instanceof Error ? e.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
