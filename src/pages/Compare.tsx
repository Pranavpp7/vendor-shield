import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import { fetchAssessments, fetchCompareAssessments } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { SCORE_POINTS, effectiveScore, isVerified } from "@/lib/scoring";
import type { Assessment as AppAssessment } from "@/types/assessment";

// Categorical series pair — deliberately distinct from the reserved
// status colors (green/amber/red mean PASS/PARTIAL/FAIL app-wide).
const VENDOR_A_COLOR = "#0d9488";
const VENDOR_B_COLOR = "#6366f1";



const STATUS_LABEL: Record<string, string> = {
  PASS: "PASS",
  PARTIAL: "PARTIAL",
  FAIL: "FAIL",
  NO_EVIDENCE: "NEEDS INFO",
};

const STATUS_CLASS: Record<string, string> = {
  PASS: "bg-risk-low-bg text-risk-low",
  PARTIAL: "bg-risk-medium-bg text-risk-medium",
  FAIL: "bg-risk-high-bg text-risk-high",
  NO_EVIDENCE: "bg-muted text-muted-foreground",
};

function scoreColor(score: number) {
  if (score >= 70) return "text-risk-low";
  if (score >= 40) return "text-risk-medium";
  return "text-risk-high";
}

function scoreLabel(score: number) {
  if (score >= 70) return "Low Risk";
  if (score >= 40) return "Medium Risk";
  return "High Risk";
}

// Raw backend shape (not the mapped frontend type)
type RawControl = {
  control_id: string;
  score: string;
  analyst_score?: string | null;
  domain: string;
  title: string;
};



type RawAssessment = {
  id: string;
  vendor_name: string;
  overall_score: number;
  domain_scores: Record<string, number>;
  control_results: RawControl[];
  created_at?: string;
};

const coverageOf = (v: RawAssessment) => {
  const controls = v.control_results ?? [];
  if (controls.length === 0) return null;
  const verified = controls.filter(isVerified).length;
  return { verified, total: controls.length, pct: Math.round((verified / controls.length) * 100) };
};

export default function Compare() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Picker
  const [assessmentList, setAssessmentList] = useState<AppAssessment[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [pickerA, setPickerA] = useState("");
  const [pickerB, setPickerB] = useState("");

  // Comparison result
  const [data, setData] = useState<RawAssessment[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 1. Load completed assessments for the picker dropdowns
  useEffect(() => {
    fetchAssessments()
      .then((list) =>
        setAssessmentList(list.filter((a) => a.status === "Completed"))
      )
      .catch(() => setAssessmentList([]))
      .finally(() => setLoadingList(false));
  }, []);

  // 2. Pre-fill picker from URL ?ids=a,b on mount
  useEffect(() => {
    const ids = (searchParams.get("ids") ?? "").split(",").filter(Boolean);
    if (ids.length === 2) {
      setPickerA(ids[0]);
      setPickerB(ids[1]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 3. Auto-fetch whenever both pickers are set (and different)
  useEffect(() => {
    if (!pickerA || !pickerB || pickerA === pickerB) {
      setData(null);
      setError(null);
      return;
    }
    // Keep URL in sync so the page is bookmarkable
    setSearchParams({ ids: `${pickerA},${pickerB}` }, { replace: true });

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCompareAssessments([pickerA, pickerB])
      .then((list) => {
        if (!cancelled) setData(list as RawAssessment[]);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? "Failed to load comparison");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pickerA, pickerB]);

  // ── Derived data ────────────────────────────────────────────────────────────

  // Bar chart rows: overall first, then one row per domain
  const barData = useMemo(() => {
    if (!data || data.length !== 2) return [];
    const [a, b] = data;
    const allDomains = new Set<string>([
      ...Object.keys(a.domain_scores ?? {}),
      ...Object.keys(b.domain_scores ?? {}),
    ]);
    return [
      { name: "Overall", A: a.overall_score, B: b.overall_score },
      ...Array.from(allDomains).map((d) => ({
        name: d,
        A: a.domain_scores?.[d] ?? 0,
        B: b.domain_scores?.[d] ?? 0,
      })),
    ];
  }, [data]);

  // Control diff rows — sorted by gap size descending
  const controlRows = useMemo(() => {
    if (!data || data.length !== 2) return [];
    const aById = new Map(
      (data[0].control_results ?? []).map((c) => [c.control_id, c])
    );
    const bById = new Map(
      (data[1].control_results ?? []).map((c) => [c.control_id, c])
    );
    const allIds = new Set([...aById.keys(), ...bById.keys()]);
    return Array.from(allIds)
      .map((id) => {
        const a = aById.get(id);
        const b = bById.get(id);
        const aScore = effectiveScore(a);
        const bScore = effectiveScore(b);
        return {
          control_id: id,
          title: a?.title ?? b?.title ?? id,
          domain: a?.domain ?? b?.domain ?? "",
          aScore,
          bScore,
          gap: Math.abs(
            (SCORE_POINTS[aScore] ?? 0) - (SCORE_POINTS[bScore] ?? 0)
          ),
        };
      })
      .sort((x, y) =>
        y.gap !== x.gap ? y.gap - x.gap : x.control_id.localeCompare(y.control_id)
      );
  }, [data]);

  const exportText = () => {
    if (!data || data.length !== 2) return;
    const [a, b] = data;
    const lines = [
      `Vendor Comparison: ${a.vendor_name} vs ${b.vendor_name}`,
      `Generated: ${new Date().toLocaleString()}`,
      "",
      `${a.vendor_name}: ${a.overall_score}/100 (${scoreLabel(a.overall_score)})`,
      `${b.vendor_name}: ${b.overall_score}/100 (${scoreLabel(b.overall_score)})`,
      "",
      "Domain Scores:",
      ...barData
        .slice(1)
        .map((r) => `  ${r.name}: ${a.vendor_name}=${r.A} | ${b.vendor_name}=${r.B}`),
      "",
      "Control Comparison (sorted by largest gap first):",
      ...controlRows.map(
        (r) =>
          `  ${r.control_id} ${r.title} [${r.domain}]: ` +
          `${a.vendor_name}=${r.aScore} | ${b.vendor_name}=${r.bScore}` +
          (r.gap > 0 ? "  ← differs" : "")
      ),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const safe = (s: string) => s.replace(/[^a-z0-9]+/gi, "_");
    link.download = `comparison-${safe(a.vendor_name)}-vs-${safe(b.vendor_name)}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const [a, b] = data ?? [];
  const hasData = !loading && !error && a && b;

  return (
    <AppLayout>
      <div className="space-y-6">

        {/* Page header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/assessments")}
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold">Vendor Comparison</h1>
              <p className="text-sm text-muted-foreground">
                Side-by-side control assessment across two vendors
              </p>
            </div>
          </div>
          {hasData && (
            <Button variant="outline" onClick={exportText}>
              <Download className="h-4 w-4 mr-2" />
              Export summary
            </Button>
          )}
        </div>

        {/* ── Picker ── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Select two completed assessments</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingList ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading assessments…
              </div>
            ) : assessmentList.length < 2 ? (
              <p className="text-sm text-muted-foreground">
                You need at least 2 completed assessments to compare. Run more
                assessments first.
              </p>
            ) : (
              <div className="flex flex-col sm:flex-row gap-6 items-start sm:items-end">
                <div className="flex-1 space-y-1.5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Vendor A
                  </p>
                  <Select value={pickerA} onValueChange={setPickerA}>
                    <SelectTrigger
                      className="border-l-4"
                      style={{ borderLeftColor: VENDOR_A_COLOR }}
                    >
                      <SelectValue placeholder="Select vendor…" />
                    </SelectTrigger>
                    <SelectContent>
                      {assessmentList.map((x) => (
                        <SelectItem
                          key={x.id}
                          value={x.id}
                          disabled={x.id === pickerB}
                        >
                          {x.vendorName} — {x.score}/100
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <span className="text-muted-foreground font-medium pb-2 hidden sm:block">
                  vs
                </span>

                <div className="flex-1 space-y-1.5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Vendor B
                  </p>
                  <Select value={pickerB} onValueChange={setPickerB}>
                    <SelectTrigger
                      className="border-l-4"
                      style={{ borderLeftColor: VENDOR_B_COLOR }}
                    >
                      <SelectValue placeholder="Select vendor…" />
                    </SelectTrigger>
                    <SelectContent>
                      {assessmentList.map((x) => (
                        <SelectItem
                          key={x.id}
                          value={x.id}
                          disabled={x.id === pickerA}
                        >
                          {x.vendorName} — {x.score}/100
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading comparison…
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* ── Comparison content (shown once both are loaded) ── */}
        {hasData && (
          <>
            {/* Overall score header cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[a, b].map((v, idx) => (
                <Card
                  key={v.id}
                  className="border-l-4"
                  style={{
                    borderLeftColor: idx === 0 ? VENDOR_A_COLOR : VENDOR_B_COLOR,
                  }}
                >
                  <CardContent className="pt-6">
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">
                      Vendor {idx === 0 ? "A" : "B"}
                    </p>
                    <h2 className="text-xl font-bold mt-1">{v.vendor_name}</h2>
                    <div className="flex items-baseline gap-2 mt-3">
                      <span
                        className={`text-4xl font-bold ${scoreColor(v.overall_score)}`}
                      >
                        {v.overall_score}
                      </span>
                      <span className="text-muted-foreground text-sm">/ 100</span>
                    </div>
                    <p
                      className={`text-sm font-medium mt-1 ${scoreColor(v.overall_score)}`}
                    >
                      {scoreLabel(v.overall_score)}
                    </p>
                    {(() => {
                      const cov = coverageOf(v);
                      return (
                        <p className="text-xs text-muted-foreground mt-2">
                          {v.created_at ? `Assessed ${formatDate(v.created_at)} · ` : ""}
                          {cov ? `coverage ${cov.pct}% (${cov.verified}/${cov.total} verified)` : ""}
                        </p>
                      );
                    })()}
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Bar chart — overall + per-domain */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Score comparison</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={barData}
                    margin={{ top: 4, right: 16, bottom: 64, left: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 11 }}
                      angle={-30}
                      textAnchor="end"
                      interval={0}
                    />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={32} />
                    <Tooltip formatter={(val) => [`${val}/100`]} />
                    <Legend
                      wrapperStyle={{ fontSize: 12, paddingTop: 12 }}
                    />
                    <Bar
                      dataKey="A"
                      name={a.vendor_name}
                      fill={VENDOR_A_COLOR}
                      radius={[4, 4, 0, 0]}
                      maxBarSize={44}
                    />
                    <Bar
                      dataKey="B"
                      name={b.vendor_name}
                      fill={VENDOR_B_COLOR}
                      radius={[4, 4, 0, 0]}
                      maxBarSize={44}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Domain winner table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Domain breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Domain</TableHead>
                      <TableHead className="text-center">{a.vendor_name}</TableHead>
                      <TableHead className="text-center">{b.vendor_name}</TableHead>
                      <TableHead className="text-center">Winner</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {barData.slice(1).map((row) => {
                      const aWins = row.A > row.B;
                      const bWins = row.B > row.A;
                      return (
                        <TableRow key={row.name}>
                          <TableCell className="font-medium">{row.name}</TableCell>
                          <TableCell
                            className={`text-center tabular-nums ${
                              aWins ? "font-bold" : "font-medium text-muted-foreground"
                            }`}
                          >
                            {row.A}
                          </TableCell>
                          <TableCell
                            className={`text-center tabular-nums ${
                              bWins ? "font-bold" : "font-medium text-muted-foreground"
                            }`}
                          >
                            {row.B}
                          </TableCell>
                          <TableCell className="text-center">
                            {row.A === row.B ? (
                              <span className="text-xs text-muted-foreground">
                                Tie
                              </span>
                            ) : (
                              <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-accent/10 text-accent border border-accent/20">
                                {aWins ? a.vendor_name : b.vendor_name}
                              </span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            {/* Control-level diff */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Control-by-control comparison
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    sorted by largest gap first
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Control</TableHead>
                      <TableHead>Domain</TableHead>
                      <TableHead>{a.vendor_name}</TableHead>
                      <TableHead>{b.vendor_name}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {controlRows.map((r) => (
                      <TableRow
                        key={r.control_id}
                        className={r.gap > 0 ? "" : "opacity-60"}
                      >
                        <TableCell>
                          <div className="font-medium text-sm">{r.control_id}</div>
                          <div className="text-xs text-muted-foreground">
                            {r.title}
                          </div>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {r.domain}
                        </TableCell>
                        <TableCell>
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                              STATUS_CLASS[r.aScore] ?? STATUS_CLASS.NO_EVIDENCE
                            }`}
                          >
                            {STATUS_LABEL[r.aScore] ?? r.aScore}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                              STATUS_CLASS[r.bScore] ?? STATUS_CLASS.NO_EVIDENCE
                            }`}
                          >
                            {STATUS_LABEL[r.bScore] ?? r.bScore}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                    {controlRows.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={4}
                          className="text-center text-muted-foreground py-8"
                        >
                          No control results available for either assessment.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </AppLayout>
  );
}
