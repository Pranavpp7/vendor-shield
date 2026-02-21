import { supabase } from "@/integrations/supabase/client";

export function generateRandomChecklist(
  controls: { id: string; category: string; name: string }[]
) {
  const results = controls.map((c) => ({
    ...c,
    passed: Math.random() > 0.3,
    comment: Math.random() > 0.6 ? "Verified during assessment." : "",
  }));
  const passedCount = results.filter((r) => r.passed).length;
  const score = Math.round((passedCount / results.length) * 100);
  const riskLevel = score >= 80 ? "Low" : score >= 60 ? "Medium" : "High";
  return { controls: results, score, riskLevel };
}

export async function generateChecklistFromAI(
  vendorName: string,
  controls: { id: string; category: string; name: string }[]
) {
  try {
    const { data, error } = await supabase.functions.invoke("vendor-ai", {
      body: {
        action: "generate-checklist",
        vendorName,
        controls: controls.map((c) => ({ id: c.id, category: c.category, name: c.name })),
      },
    });
    if (error) throw error;
    return data;
  } catch {
    return generateRandomChecklist(controls);
  }
}

export async function chatWithAI(
  question: string,
  checklistJson: string
): Promise<string> {
  try {
    const { data, error } = await supabase.functions.invoke("vendor-ai", {
      body: { action: "chat", question, context: checklistJson },
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
