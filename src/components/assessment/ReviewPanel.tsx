import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, ShieldAlert, UserCheck } from "lucide-react";
import { toast } from "sonner";
import { overrideControlScore } from "@/lib/api";
import { BackendScore, ControlResult } from "@/types/assessment";

const SCORE_OPTIONS: BackendScore[] = ["PASS", "PARTIAL", "FAIL", "NO_EVIDENCE"];
const NO_OVERRIDE = "__ai__";

const scoreBadgeClass: Record<string, string> = {
  PASS: "bg-emerald-500/15 text-emerald-600",
  PARTIAL: "bg-amber-500/15 text-amber-600",
  FAIL: "bg-red-500/15 text-red-600",
  NO_EVIDENCE: "bg-muted text-muted-foreground",
};

type Props = {
  assessmentId: string;
  controls: ControlResult[];
  onUpdated: () => void;
};

/**
 * Human-in-the-loop review queue: shows every control with its AI score,
 * confidence, and an override selector. The AI score is never lost — an
 * override sits alongside it as the effective score, with an audit trail.
 */
export function ReviewPanel({ assessmentId, controls, onUpdated }: Props) {
  const [drafts, setDrafts] = useState<Record<string, { score: string; comment: string }>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const draftFor = (c: ControlResult) =>
    drafts[c.id] ?? {
      score: c.analystScore ?? NO_OVERRIDE,
      comment: c.analystComment ?? "",
    };

  const isDirty = (c: ControlResult) => {
    const d = draftFor(c);
    const current = c.analystScore ?? NO_OVERRIDE;
    return d.score !== current || d.comment !== (c.analystComment ?? "");
  };

  const save = async (c: ControlResult) => {
    const d = draftFor(c);
    setSaving(c.id);
    try {
      const result = await overrideControlScore(
        assessmentId,
        c.id,
        d.score === NO_OVERRIDE ? null : (d.score as BackendScore),
        d.comment
      );
      toast.success(
        d.score === NO_OVERRIDE
          ? `Override cleared on ${c.id} — score ${result.overall_score}/100`
          : `${c.id} overridden to ${d.score} — score now ${result.overall_score}/100`
      );
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[c.id];
        return next;
      });
      onUpdated();
    } catch (err: any) {
      toast.error(`Override failed: ${err.message}`);
    } finally {
      setSaving(null);
    }
  };

  const needsReviewCount = controls.filter((c) => c.needsReview).length;
  const overriddenCount = controls.filter((c) => c.analystScore).length;

  // Low-confidence, unreviewed controls first; then by id
  const sorted = [...controls].sort((a, b) => {
    if (!!a.needsReview !== !!b.needsReview) return a.needsReview ? -1 : 1;
    return a.id.localeCompare(b.id);
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <UserCheck className="h-4 w-4" />
          Analyst Review
          {needsReviewCount > 0 && (
            <Badge variant="outline" className="text-amber-600 border-amber-400">
              {needsReviewCount} need review
            </Badge>
          )}
          {overriddenCount > 0 && (
            <Badge variant="outline">{overriddenCount} overridden</Badge>
          )}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          The AI verdict is a first pass. Confirm or override each score — the
          original AI score is preserved as an audit trail and all totals are
          recalculated from your decisions.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {sorted.map((c) => {
          const d = draftFor(c);
          return (
            <div
              key={c.id}
              className={`rounded-lg border p-3 space-y-2 ${
                c.needsReview ? "border-amber-400/50 bg-amber-500/5" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium">
                    {c.id} — {c.name}
                  </span>
                  <Badge className={scoreBadgeClass[c.aiScore ?? ""] ?? ""}>
                    AI: {c.aiScore}
                  </Badge>
                  {typeof c.confidence === "number" && (
                    <span className="text-xs text-muted-foreground">
                      confidence {(c.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  {c.needsReview && (
                    <Badge variant="outline" className="text-amber-600 border-amber-400">
                      <ShieldAlert className="h-3 w-3 mr-1" />
                      low confidence
                    </Badge>
                  )}
                  {c.analystScore && (
                    <Badge className="bg-blue-500/15 text-blue-600">
                      Analyst: {c.analystScore}
                    </Badge>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Select
                  value={d.score}
                  onValueChange={(v) =>
                    setDrafts((prev) => ({ ...prev, [c.id]: { ...d, score: v } }))
                  }
                >
                  <SelectTrigger className="h-8 w-56">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_OVERRIDE}>Keep AI score</SelectItem>
                    {SCORE_OPTIONS.map((s) => (
                      <SelectItem key={s} value={s}>
                        Override to {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  className="h-8 flex-1 min-w-[200px]"
                  placeholder="Why? (kept in the audit trail)"
                  value={d.comment}
                  onChange={(e) =>
                    setDrafts((prev) => ({ ...prev, [c.id]: { ...d, comment: e.target.value } }))
                  }
                />
                <Button
                  size="sm"
                  className="h-8"
                  disabled={!isDirty(c) || saving === c.id}
                  onClick={() => save(c)}
                >
                  {saving === c.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save"}
                </Button>
              </div>
            </div>
          );
        })}
        {controls.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Run the assessment first — there are no scored controls to review yet.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
