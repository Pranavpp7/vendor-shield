import { supabase } from "@/integrations/supabase/client";
import { ControlResult } from "@/types/assessment";

export async function saveRunSnapshot(
  assessmentId: string,
  userId: string,
  score: number,
  riskLevel: string,
  controls: ControlResult[]
) {
  const passed = controls.filter((c) => c.status === "passed").length;
  const failed = controls.filter((c) => c.status === "failed").length;
  const needsInfo = controls.filter((c) => c.status === "needs_info").length;

  const { error } = await supabase.from("assessment_runs" as any).insert({
    assessment_id: assessmentId,
    user_id: userId,
    score,
    risk_level: riskLevel,
    passed_count: passed,
    failed_count: failed,
    needs_info_count: needsInfo,
    controls,
  });

  if (error) {
    console.error("Failed to save run snapshot:", error);
  }
}

export type RunRecord = {
  id: string;
  score: number;
  riskLevel: string;
  passedCount: number;
  failedCount: number;
  needsInfoCount: number;
  runAt: string;
};

export async function fetchRunHistory(assessmentId: string): Promise<RunRecord[]> {
  const { data, error } = await supabase
    .from("assessment_runs" as any)
    .select("id, score, risk_level, passed_count, failed_count, needs_info_count, run_at")
    .eq("assessment_id", assessmentId)
    .order("run_at", { ascending: true });

  if (error) {
    console.error("Failed to fetch run history:", error);
    return [];
  }

  return (data || []).map((r: any) => ({
    id: r.id,
    score: r.score,
    riskLevel: r.risk_level,
    passedCount: r.passed_count,
    failedCount: r.failed_count,
    needsInfoCount: r.needs_info_count,
    runAt: r.run_at,
  }));
}
