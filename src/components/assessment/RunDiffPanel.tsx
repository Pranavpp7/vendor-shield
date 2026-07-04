import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowRight,
  GitCompareArrows,
  Loader2,
  MinusCircle,
  PlusCircle,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
  Equal,
  Shuffle,
} from "lucide-react";
import {
  AssessmentDiff,
  fetchAssessmentDiff,
  fetchVendorHistory,
  VendorHistoryEntry,
} from "@/lib/api";

// Direction treatments — icon + text always accompany the color, so the
// signal survives grayscale and CVD. Colors are the validated status set.
const DIRECTION = {
  improved: { icon: TrendingUp, text: "text-[#16a34a]", bg: "bg-[#16a34a]/10", label: "Improved" },
  regressed: { icon: TrendingDown, text: "text-[#dc2626]", bg: "bg-[#dc2626]/10", label: "Regressed" },
  changed: { icon: Shuffle, text: "text-[#d97706]", bg: "bg-[#d97706]/10", label: "Changed" },
  unchanged: { icon: Equal, text: "text-muted-foreground", bg: "bg-muted/50", label: "Unchanged" },
  added: { icon: PlusCircle, text: "text-accent", bg: "bg-accent/10", label: "Added" },
  removed: { icon: MinusCircle, text: "text-muted-foreground", bg: "bg-muted/50", label: "Removed" },
} as const;

const fmtDate = (iso: string) => {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short", day: "numeric", year: "numeric",
    });
  } catch {
    return iso;
  }
};

type Props = {
  vendorName: string;
  currentAssessmentId: string;
};

/**
 * Compare two assessment runs of the same vendor, control by control.
 * Defaults to previous-vs-current; both sides are selectable. Uses the
 * backend diff endpoint (effective, override-aware scores).
 */
export function RunDiffPanel({ vendorName, currentAssessmentId }: Props) {
  const [history, setHistory] = useState<VendorHistoryEntry[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [baseId, setBaseId] = useState<string>("");
  const [compareId, setCompareId] = useState<string>("");
  const [diff, setDiff] = useState<AssessmentDiff | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changesOnly, setChangesOnly] = useState(true);

  // Load this vendor's runs and default to previous → current
  useEffect(() => {
    fetchVendorHistory(vendorName)
      .then((entries) => {
        setHistory(entries);
        if (entries.length >= 2) {
          const currentIdx = entries.findIndex((e) => e.id === currentAssessmentId);
          const compare = currentIdx >= 0 ? entries[currentIdx] : entries[entries.length - 1];
          const baseCandidates = entries.filter((e) => e.id !== compare.id);
          const base = baseCandidates[baseCandidates.length - 1];
          setBaseId(base.id);
          setCompareId(compare.id);
        }
      })
      .catch((err) => console.error("Vendor history load failed:", err))
      .finally(() => setHistoryLoaded(true));
  }, [vendorName, currentAssessmentId]);

  // Fetch the diff whenever the selection changes
  useEffect(() => {
    if (!baseId || !compareId || baseId === compareId) return;
    setLoading(true);
    setError(null);
    fetchAssessmentDiff(baseId, compareId)
      .then(setDiff)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [baseId, compareId]);

  const rows = useMemo(() => {
    if (!diff) return [];
    return changesOnly
      ? diff.controls.filter((c) => c.direction !== "unchanged")
      : diff.controls;
  }, [diff, changesOnly]);

  if (historyLoaded && history.length < 2) {
    return null; // nothing to compare yet — VendorTrendView explains the trend story
  }

  const delta = diff?.score_delta ?? 0;

  return (
    <Card>
      <CardHeader className="space-y-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <GitCompareArrows className="h-4 w-4" />
          Compare Runs
        </CardTitle>
        <div className="flex items-center gap-2 flex-wrap">
          <Select value={baseId} onValueChange={setBaseId}>
            <SelectTrigger className="h-8 w-[210px]">
              <SelectValue placeholder="Baseline run" />
            </SelectTrigger>
            <SelectContent>
              {history.map((h) => (
                <SelectItem key={h.id} value={h.id} disabled={h.id === compareId}>
                  {fmtDate(h.created_at)} — {h.score}/100
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
          <Select value={compareId} onValueChange={setCompareId}>
            <SelectTrigger className="h-8 w-[210px]">
              <SelectValue placeholder="Comparison run" />
            </SelectTrigger>
            <SelectContent>
              {history.map((h) => (
                <SelectItem key={h.id} value={h.id} disabled={h.id === baseId}>
                  {fmtDate(h.created_at)} — {h.score}/100
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-2 ml-auto">
            <Switch id="changes-only" checked={changesOnly} onCheckedChange={setChangesOnly} />
            <Label htmlFor="changes-only" className="text-xs text-muted-foreground">
              Changes only
            </Label>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <p className="text-sm text-risk-high">{error}</p>
        ) : diff ? (
          <>
            {/* Headline: score movement */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold tabular-nums">{diff.base.overall_score}</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground self-center" />
                <span className="text-2xl font-bold tabular-nums">{diff.compare.overall_score}</span>
              </div>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                  delta > 0
                    ? `${DIRECTION.improved.bg} ${DIRECTION.improved.text}`
                    : delta < 0
                    ? `${DIRECTION.regressed.bg} ${DIRECTION.regressed.text}`
                    : `${DIRECTION.unchanged.bg} ${DIRECTION.unchanged.text}`
                }`}
              >
                {delta > 0 ? <TrendingUp className="h-3 w-3" /> : delta < 0 ? <TrendingDown className="h-3 w-3" /> : <Equal className="h-3 w-3" />}
                {delta > 0 ? `+${delta}` : delta} points
              </span>
              {/* Summary chips */}
              <div className="flex items-center gap-1.5 ml-auto flex-wrap">
                {(["improved", "regressed", "changed", "unchanged"] as const).map((key) => {
                  const count = diff.summary[key];
                  if (count === 0) return null;
                  const d = DIRECTION[key];
                  return (
                    <span
                      key={key}
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${d.bg} ${d.text}`}
                    >
                      <d.icon className="h-3 w-3" />
                      {count} {d.label.toLowerCase()}
                    </span>
                  );
                })}
              </div>
            </div>

            {diff.framework_mismatch && (
              <p className="text-xs text-amber-600 flex items-center gap-1.5">
                <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
                These runs used different frameworks — control-level comparison is
                approximate.
              </p>
            )}

            {/* Per-control rows */}
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground py-2">
                No control-level changes between these runs.
              </p>
            ) : (
              <div className="divide-y rounded-lg border">
                {rows.map((c) => {
                  const d = DIRECTION[c.direction];
                  return (
                    <div key={c.control_id} className="flex items-center gap-3 px-3 py-2 text-sm">
                      <span className={`h-6 w-6 rounded-full flex items-center justify-center shrink-0 ${d.bg}`}>
                        <d.icon className={`h-3.5 w-3.5 ${d.text}`} />
                      </span>
                      <div className="flex-1 min-w-0">
                        <span className="font-medium">{c.control_id}</span>
                        <span className="text-muted-foreground"> — {c.title}</span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0 text-xs tabular-nums">
                        <Badge variant="outline" className="font-mono">
                          {c.base_score ?? "—"}
                        </Badge>
                        <ArrowRight className="h-3 w-3 text-muted-foreground" />
                        <Badge variant="outline" className="font-mono">
                          {c.compare_score ?? "—"}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Select two runs to compare.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
