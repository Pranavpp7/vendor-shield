import { Assessment, ControlResult, ControlStatus, DomainScore } from "@/types/assessment";

export function scoreToStatus(s: string): ControlStatus {
  if (s === "PASS") return "passed";
  if (s === "FAIL") return "failed";
  if (s === "PARTIAL") return "partial";
  return "needs_info";
}

export function mapControl(r: any): ControlResult {
  // The effective score is what the UI shows: analyst override wins,
  // the AI score stays available as the audit trail.
  const effective: string = r.analyst_score || r.score;
  return {
    id: r.control_id,
    category: r.domain,
    name: r.title,
    passed: effective === "PASS",
    status: scoreToStatus(effective),
    comment: "",
    aiExplanation: r.reasoning,
    evidenceSource: r.evidence_quote || "No evidence found",
    citations: r.citations || [],
    confidence: r.confidence,
    gap: r.gap,
    aiScore: r.score,
    analystScore: r.analyst_score ?? null,
    analystComment: r.analyst_comment ?? null,
    overriddenAt: r.overridden_at ?? null,
    needsReview: r.needs_review ?? false,
  };
}

export function mapDomainScores(
  dict: Record<string, number> | undefined,
  rawControls: any[]
): DomainScore[] {
  if (!dict) return [];
  const eff = (r: any): string => r.analyst_score || r.score;
  return Object.entries(dict).map(([domain, score]) => {
    const dc = rawControls.filter((r) => r.domain === domain);
    return {
      domain,
      score: score as number,
      total_controls: dc.length,
      passed: dc.filter((r) => eff(r) === "PASS").length,
      partial: dc.filter((r) => eff(r) === "PARTIAL").length,
      failed: dc.filter((r) => eff(r) === "FAIL").length,
      no_evidence: dc.filter((r) => eff(r) === "NO_EVIDENCE").length,
    };
  });
}

export function mapBackendAssessment(row: any): Assessment {
  const rawControls = row.control_results || [];
  // Coverage is computed from the effective (override-aware) scores so an
  // analyst overriding NO_EVIDENCE to a real verdict raises coverage live.
  const verified = rawControls.filter(
    (r: any) => (r.analyst_score || r.score) !== "NO_EVIDENCE"
  ).length;
  const evidenceCoverage =
    rawControls.length > 0
      ? {
          verified,
          total: rawControls.length,
          pct: Math.round((verified / rawControls.length) * 100),
        }
      : null;
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
    frameworkId: row.framework_id || "nist-800-53",
    reviewQueue: row.review_queue || [],
    evidenceCoverage,
    runHistory: (row.run_history || []).map((r: any) => ({
      score: r.score ?? 0,
      ranAt: r.ran_at || "",
    })),
    runMetrics: row.run_metrics
      ? {
          llmCalls: row.run_metrics.llm_calls ?? 0,
          promptTokens: row.run_metrics.prompt_tokens ?? 0,
          completionTokens: row.run_metrics.completion_tokens ?? 0,
          estimatedCostUsd: row.run_metrics.estimated_cost_usd ?? 0,
          durationSeconds: row.run_metrics.duration_seconds ?? 0,
        }
      : null,
    riskProfile: row.risk_profile || null,
    inherentRisk: row.inherent_risk
      ? { tier: row.inherent_risk.tier, points: row.inherent_risk.points }
      : null,
    residualRisk: row.residual_risk || null,
    evidenceFreshness: row.evidence_freshness || null,
  };
}
