/** THE canonical frontend scoring rules — the mirror of the backend's
 *  models/controls.py (effective_score + SCORE_MAP).  Every component
 *  that needs "which score counts" or "what is a score worth" imports
 *  from here; nothing re-derives these inline.  If the backend rule
 *  ever changes, this is the ONLY frontend file to touch. */

export type RawScoredControl = {
  score?: string | null;
  analyst_score?: string | null;
};

/** Analyst override supersedes the AI verdict; absent everything = unverified. */
export function effectiveScore(c: RawScoredControl | undefined | null): string {
  if (!c) return "NO_EVIDENCE";
  return c.analyst_score || c.score || "NO_EVIDENCE";
}

/** Point value of a VERIFIED score (mirror of backend SCORE_MAP).
 *  NO_EVIDENCE is deliberately 0 — an unverifiable control earns nothing. */
export const SCORE_POINTS: Record<string, number> = {
  PASS: 1.0,
  PARTIAL: 0.5,
  FAIL: 0.0,
  NO_EVIDENCE: 0.0,
};

export const isVerified = (c: RawScoredControl | undefined | null): boolean =>
  effectiveScore(c) !== "NO_EVIDENCE";
