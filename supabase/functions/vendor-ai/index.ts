import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const AI_GATEWAY = "https://ai.gateway.lovable.dev/v1/chat/completions";

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY is not configured");

    const { action, ...params } = await req.json();
    let messages: { role: string; content: string }[];
    let maxTokens = 800;

    // RAG: retrieve document context if assessment_id is provided
    let ragContext = "";
    if (params.assessmentId && (action === "chat" || action === "generate-checklist" || action === "generate-summary")) {
      try {
        const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
        const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
        const supabase = createClient(supabaseUrl, supabaseKey);

        // Build search query from the user's question or vendor name
        const searchQuery = action === "chat" 
          ? params.question 
          : action === "generate-checklist"
          ? params.vendorName + " security compliance controls"
          : params.vendorName + " risk assessment summary";

        const { data: chunks } = await supabase.rpc("search_document_chunks", {
          p_assessment_id: params.assessmentId,
          p_query: searchQuery,
          p_limit: 8,
        });

        if (chunks && chunks.length > 0) {
          ragContext = "\n\n--- RETRIEVED DOCUMENT CONTEXT ---\n" +
            chunks.map((c: any) => `[Source: ${c.file_name}, Section ${c.chunk_index + 1}]:\n${c.content}`).join("\n\n") +
            "\n--- END DOCUMENT CONTEXT ---\n";
        }
      } catch (ragErr) {
        console.error("RAG retrieval error (non-fatal):", ragErr);
      }
    }

    if (action === "generate-checklist") {
      const controlNames = params.controls
        .map((c: { id: string; name: string }) => `${c.id}: ${c.name}`)
        .join("\n");
      messages = [
        {
          role: "system",
          content:
            'You are generating FAKE but realistic test data for a vendor security checklist. Always respond with valid JSON only, no markdown code blocks.' +
            (ragContext ? '\n\nUse the following document evidence to ground your assessment. Reference specific documents in aiExplanation fields.' + ragContext : ''),
        },
        {
          role: "user",
          content: `Generate random but realistic assessment results for vendor "${params.vendorName}" with these security controls:\n${controlNames}\n\nEach control should have a status of "passed", "failed", or "needs_info" (use needs_info when additional documentation is required from the vendor).\n\nReturn JSON: { "results": [{ "id": "<control_id>", "status": "passed"|"failed"|"needs_info", "comment": "short comment or empty string", "aiExplanation": "2-3 sentence explanation of why this verdict was given, referencing specific evidence or gaps" }], "score": <0-100 integer>, "riskLevel": "Low"|"Medium"|"High" }\n\nMake roughly 65-80% pass, 5-15% needs_info, rest failed. Score should reflect pass rate. Ensure valid JSON.`,
        },
      ];
      maxTokens = 1200;
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
        temperature: action === "generate-checklist" ? 0.9 : 0.7,
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
          const status = result?.status || (result?.passed ? "passed" : result?.passed === false ? "failed" : "passed");
          return {
            ...c,
            passed: status === "passed",
            status,
            comment: result?.comment ?? "",
            aiExplanation: result?.aiExplanation ?? "",
          };
        });
        return new Response(
          JSON.stringify({
            controls,
            score: parsed.score ?? 70,
            riskLevel: parsed.riskLevel ?? "Medium",
          }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      } catch (parseErr) {
        console.error("JSON parse error:", parseErr, "Content:", content);
        const controls = params.controls.map((c: { id: string; category: string; name: string }) => ({
          ...c,
          passed: Math.random() > 0.3,
          status: Math.random() > 0.85 ? "needs_info" : (Math.random() > 0.3 ? "passed" : "failed"),
          comment: "",
          aiExplanation: "",
        }));
        const passedCount = controls.filter((c: { passed: boolean }) => c.passed).length;
        const score = Math.round((passedCount / controls.length) * 100);
        return new Response(
          JSON.stringify({
            controls,
            score,
            riskLevel: score >= 80 ? "Low" : score >= 60 ? "Medium" : "High",
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
