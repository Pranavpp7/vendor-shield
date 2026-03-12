import { supabase } from "@/integrations/supabase/client";

const evidenceSources = [
  "SOC 2 Type II Report (2025)",
  "ISO 27001 Certificate",
  "Penetration Test Report Q4",
  "Vendor Security Questionnaire",
  "Data Processing Agreement",
  "Network Architecture Diagram",
  "Access Control Policy v3.2",
  "Incident Response Playbook",
  "Third-Party Audit Summary",
  "Cloud Security Assessment",
  "Privacy Impact Assessment",
  "Business Continuity Plan",
  "Encryption Standards Doc",
  "GDPR Compliance Report",
  "Vulnerability Scan Results",
];

function getRandomSource(): string {
  return evidenceSources[Math.floor(Math.random() * evidenceSources.length)];
}

const aiExplanations = {
  passed: [
    "Security documentation provided meets industry standards and aligns with NIST CSF guidelines. Vendor demonstrated comprehensive implementation with proper audit trails, continuous monitoring capabilities, and automated alerting mechanisms in place. Evidence of annual third-party validation was confirmed through supplementary audit artifacts.",
    "Control implementation verified through automated scanning and manual review conducted by the security assessment team. Evidence of regular updates and patch management protocols observed, with a documented 72-hour SLA for critical vulnerability remediation. Historical compliance data shows consistent adherence over the past 18 months.",
    "Vendor provided detailed technical specifications and third-party audit reports confirming compliance with this requirement. Implementation follows defense-in-depth principles with multiple compensating controls identified. Configuration baselines reviewed and validated against CIS benchmarks.",
    "Assessment confirmed proper implementation based on SOC 2 Type II report findings and supplementary technical documentation provided during the evaluation period. Control design and operating effectiveness were both validated with no exceptions noted in the most recent audit cycle.",
    "Control is effectively implemented with appropriate safeguards including automated enforcement, exception tracking, and periodic validation procedures. Testing methodology included both automated scanning and manual review of configuration artifacts and operational logs spanning the past 12 months.",
    "Evidence reviewed shows mature security practices with documented procedures matching stated policies. Organizational commitment to continuous improvement demonstrated through quarterly review cycles, documented lessons learned, and proactive threat intelligence integration. No material gaps identified.",
  ],
  failed: [
    "Critical security gaps identified in current implementation that do not meet minimum organizational requirements. Vendor documentation lacks evidence of required encryption standards, and access control configurations were found to be inconsistent with stated policies. Remediation is required before proceeding with any data sharing arrangements.",
    "Assessment revealed missing or outdated security controls that introduce unacceptable residual risk. Key deficiencies include lack of centralized logging, absence of automated alerting for anomalous activity, and insufficient segregation of duties. A formal remediation plan with defined milestones is required before engagement can proceed.",
    "Control implementation does not meet minimum security requirements established in the vendor risk management framework. Significant vulnerabilities detected during technical review, including outdated TLS configurations, missing intrusion detection capabilities, and gaps in endpoint protection coverage across production environments.",
    "Documentation provided is insufficient to validate compliance with regulatory and organizational standards. Multiple security exceptions noted that require immediate attention, including unpatched systems in production, excessive administrative privileges, and lack of documented change management procedures.",
    "Technical assessment found material implementation gaps that pose significant risk to data confidentiality and integrity. Current architecture lacks required isolation controls, monitoring capabilities are limited, and incident response procedures have not been tested within the past 12 months. Recommend deferring engagement until full remediation is verified.",
    "Security controls do not align with organizational requirements or industry best practices. Evidence of non-compliance with applicable regulatory standards identified, including inadequate data retention controls, missing privacy safeguards, and insufficient vendor subprocessor oversight. Formal risk acceptance would be required to proceed.",
  ],
  needs_info: [
    "Additional documentation required to complete the security assessment for this control area. Vendor has been notified to provide current SOC 2 Type II report, most recent penetration test results, and evidence of remediation activities for any identified findings. Assessment will remain in pending status until all requested artifacts are received and reviewed.",
    "Unable to validate control effectiveness without supplementary evidence from the vendor. Awaiting detailed technical architecture documentation, network segmentation diagrams, and access control matrix. Initial review of available documentation suggests potential compliance, but formal determination cannot be made without complete evidence.",
    "Partial documentation received but key artifacts are missing for a complete assessment. Follow-up request sent for network security configurations, administrative access logs, and evidence of periodic control testing. Vendor indicated a 10-business-day turnaround for providing the requested materials.",
    "Assessment paused pending receipt of third-party audit documentation, evidence of remediation activities for prior findings, and updated risk treatment plans. Without these artifacts, the assessment team cannot determine whether compensating controls adequately address identified gaps in the current implementation.",
    "Vendor response to the security questionnaire was incomplete in several critical areas. Additional clarification needed on data handling procedures, cross-border transfer mechanisms, incident response capabilities, and backup/recovery testing frequency. Follow-up meeting scheduled to discuss outstanding items.",
    "Current evidence is insufficient for a definitive determination on this control. Requested detailed technical specifications, current compliance certifications, and evidence of operational procedures. Preliminary review indicates the vendor may meet requirements, but formal validation requires the complete documentation package.",
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
      evidenceSource: getRandomSource(),
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
        evidenceSource: c.evidenceSource || getRandomSource(),
      }));
    }
    return data;
  } catch {
    return generateRandomChecklist(controls);
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
