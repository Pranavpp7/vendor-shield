import { ControlResult } from "@/types/assessment";

/** THE single definition of "needs analyst judgment" — used by BOTH the
 *  Review tab badge and the ReviewPanel list so they can never drift.
 *
 *  In the queue: controls with no analyst verdict yet whose effective
 *  status is unverified (needs_info), inconclusive (partial), or whose
 *  AI confidence was low.  PASS/FAIL with decent confidence are settled
 *  verdicts — still overridable from the "All controls" view, but not
 *  forced into the queue. */
export function needsAnalystJudgment(c: ControlResult): boolean {
  if (c.analystScore) return false; // judgment already given
  return c.status === "needs_info" || c.status === "partial" || !!c.needsReview;
}

export function reviewQueue(controls: ControlResult[]): ControlResult[] {
  return controls.filter(needsAnalystJudgment);
}
