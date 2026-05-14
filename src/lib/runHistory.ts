export type RunRecord = {
  id: string;
  score: number;
  riskLevel: string;
  passedCount: number;
  failedCount: number;
  needsInfoCount: number;
  partialCount: number;
  runAt: string;
};

import { apiFetch } from "@/lib/api";

export async function fetchRunHistory(assessmentId: string): Promise<RunRecord[]> {
  try {
    const res = await apiFetch(`/api/assessments/${assessmentId}/run-history`);
    if (!res.ok) return [];
    const data = await res.json();
    return (data.run_history || []).map((r: any): RunRecord => ({
      id: r.run_id,
      score: r.score ?? 0,
      riskLevel: r.risk_level ?? "High",
      passedCount: r.pass_count ?? 0,
      failedCount: r.fail_count ?? 0,
      needsInfoCount: r.no_evidence_count ?? 0,
      partialCount: r.partial_count ?? 0,
      runAt: r.ran_at,
    }));
  } catch {
    return [];
  }
}
