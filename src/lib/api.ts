import { supabase } from "@/integrations/supabase/client";

export async function generateChecklistFromAI(
  vendorName: string,
  controls: { id: string; category: string; name: string }[],
  assessmentId?: string
) {
  try {
    const { data, error } = await supabase.functions.invoke("vendor-ai", {
      body: {
        action: "generate-checklist",
        vendorName,
        controls: controls.map((c) => ({ id: c.id, category: c.category, name: c.name })),
        assessmentId,
      },
    });
    if (error) throw error;
    return data;
  } catch (err) {
    console.error("Checklist generation failed:", err);
    // Fallback: all needs_info
    const fallbackControls = controls.map((c) => ({
      ...c,
      passed: false,
      status: "needs_info" as const,
      comment: "",
      aiExplanation: "Unable to connect to AI service. Please re-run the checklist.",
      evidenceSource: "Service unavailable",
    }));
    return {
      controls: fallbackControls,
      score: 0,
      riskLevel: "High",
    };
  }
}

export async function chatWithAI(
  question: string,
  checklistJson: string,
  assessmentId?: string
): Promise<string> {
  try {
    const { data, error } = await supabase.functions.invoke("vendor-ai", {
      body: { action: "chat", question, context: checklistJson, assessmentId },
    });
    if (error) throw error;
    return data.reply;
  } catch {
    return "Unable to connect to AI service. Please review the checklist results directly.";
  }
}

export async function generateSummaryFromAI(
  vendorName: string,
  score: number,
  riskLevel: string,
  controls: any[],
  notes: string
): Promise<string> {
  try {
    const { data, error } = await supabase.functions.invoke("vendor-ai", {
      body: { action: "generate-summary", vendorName, score, riskLevel, controls, notes },
    });
    if (error) throw error;
    return data.summary;
  } catch {
    const failed = controls.filter((c: any) => !c.passed).length;
    return `## Vendor Risk Summary: ${vendorName}\n\n**Overall Score:** ${score}/100 | **Risk Level:** ${riskLevel}\n\nEvaluated ${controls.length} controls. ${failed} controls did not meet requirements.\n\n${notes ? `**Analyst Notes:** ${notes}` : "No analyst notes recorded."}`;
  }
}
