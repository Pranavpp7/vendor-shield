import { Assessment, ControlResult, ControlStatus, DomainScore } from "@/types/assessment";

export function scoreToStatus(s: string): ControlStatus {
  if (s === "PASS") return "passed";
  if (s === "FAIL") return "failed";
  if (s === "PARTIAL") return "partial";
  return "needs_info";
}

export function mapControl(r: any): ControlResult {
  return {
    id: r.control_id,
    category: r.domain,
    name: r.title,
    passed: r.score === "PASS",
    status: scoreToStatus(r.score),
    comment: "",
    aiExplanation: r.reasoning,
    evidenceSource: r.evidence_quote || "No evidence found",
    citations: r.citations || [],
    confidence: r.confidence,
    gap: r.gap,
  };
}

export function mapDomainScores(
  dict: Record<string, number> | undefined,
  rawControls: any[]
): DomainScore[] {
  if (!dict) return [];
  return Object.entries(dict).map(([domain, score]) => {
    const dc = rawControls.filter((r) => r.domain === domain);
    return {
      domain,
      score: score as number,
      total_controls: dc.length,
      passed: dc.filter((r) => r.score === "PASS").length,
      partial: dc.filter((r) => r.score === "PARTIAL").length,
      failed: dc.filter((r) => r.score === "FAIL").length,
      no_evidence: dc.filter((r) => r.score === "NO_EVIDENCE").length,
    };
  });
}

export function mapBackendAssessment(row: any): Assessment {
  const rawControls = row.control_results || [];
  const rawStatus: string = row.status || "completed";
  const status = (
    rawStatus.charAt(0).toUpperCase() + rawStatus.slice(1)
  ) as Assessment["status"];
  return {
    id: row.id,
    vendorName: row.vendor_name,
    criticality: row.criticality || "Medium",
    createdAt: row.created_at,
    status,
    score: row.overall_score ?? 0,
    riskLevel: row.risk_level || "High",
    controls: rawControls.map(mapControl),
    notes: row.notes || "",
    chatHistory: row.chat_history || [],
    uploadedFiles: row.uploaded_files || [],
    links: row.links || [],
    domainScores: mapDomainScores(row.domain_scores, rawControls),
    gapsSummary: row.gaps_summary,
    warning: row.warning,
    error: row.error,
  };
}
