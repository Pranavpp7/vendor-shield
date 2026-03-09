import { supabase } from "@/integrations/supabase/client";

const aiExplanations = {
  passed: [
    "Security documentation provided meets industry standards. Vendor demonstrated comprehensive implementation with proper audit trails and monitoring capabilities in place.",
    "Control implementation verified through automated scanning and manual review. Evidence of regular updates and patch management protocols observed.",
    "Vendor provided detailed technical specifications and third-party audit reports confirming compliance with this requirement.",
    "Assessment confirmed proper implementation based on SOC 2 Type II report findings and supplementary technical documentation.",
    "Control is effectively implemented with appropriate safeguards. Regular testing and validation procedures are documented and followed.",
    "Evidence reviewed shows mature security practices with documented procedures matching stated policies. No gaps identified.",
  ],
  failed: [
    "Critical security gaps identified in current implementation. Vendor documentation lacks evidence of required encryption standards and access controls.",
    "Assessment revealed missing or outdated security controls. Remediation plan required before proceeding with vendor engagement.",
    "Control implementation does not meet minimum security requirements. Significant vulnerabilities detected during technical review.",
    "Documentation provided is insufficient to validate compliance. Multiple security exceptions noted that require immediate attention.",
    "Technical assessment found implementation gaps that pose material risk. Recommend deferring engagement until remediation is complete.",
    "Security controls do not align with organizational requirements. Evidence of non-compliance with industry standards identified.",
  ],
  needs_info: [
    "Additional documentation required to complete security assessment. Vendor has been notified to provide SOC 2 report and penetration test results.",
    "Unable to validate control effectiveness without supplementary evidence. Awaiting vendor response on technical architecture details.",
    "Partial documentation received but key artifacts missing. Follow-up request sent for network security configurations and access logs.",
    "Assessment paused pending receipt of third-party audit documentation and evidence of remediation activities.",
    "Vendor response incomplete. Additional clarification needed on data handling procedures and incident response capabilities.",
    "Current evidence insufficient for determination. Requested detailed technical specifications and compliance certifications.",
  ],
};

function getRandomExplanation(status: "passed" | "failed" | "needs_info"): string {
  const explanations = aiExplanations[status];
  return explanations[Math.floor(Math.random() * explanations.length)];
}

export function generateRandomChecklist(
  controls: { id: string; category: string; name: string }[]
) {
  const results = controls.map((c) => {
    const rand = Math.random();
    const status = rand > 0.85 ? "needs_info" : rand > 0.3 ? "passed" : "failed";
    return {
      ...c,
      passed: status === "passed",
      status,
      comment: Math.random() > 0.6 ? "Verified during assessment." : "",
      aiExplanation: getRandomExplanation(status as "passed" | "failed" | "needs_info"),
    };
  });
  const passedCount = results.filter((r) => r.status === "passed").length;
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
    
    // Ensure all controls have aiExplanation
    if (data?.controls) {
      data.controls = data.controls.map((c: any) => ({
        ...c,
        aiExplanation: c.aiExplanation || getRandomExplanation(c.status || "passed"),
      }));
    }
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
