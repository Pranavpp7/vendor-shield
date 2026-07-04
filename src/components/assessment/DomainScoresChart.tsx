import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DomainScore } from "@/types/assessment";
import { BarChart3, CheckCircle2, MinusCircle, XCircle, HelpCircle } from "lucide-react";

// Status palette validated against the light surface (3:1+ contrast,
// CVD-separated). The gray is a semantic neutral for "no evidence";
// every segment also carries an icon + count chip, never color alone.
const SEGMENTS = [
  { key: "passed", color: "#16a34a", label: "Passed", icon: CheckCircle2 },
  { key: "partial", color: "#d97706", label: "Partial", icon: MinusCircle },
  { key: "failed", color: "#dc2626", label: "Failed", icon: XCircle },
  { key: "no_evidence", color: "#64748b", label: "No evidence", icon: HelpCircle },
] as const;

const CHIP_STYLES: Record<string, string> = {
  passed: "bg-[#16a34a]/10 text-[#15803d] border-[#16a34a]/25",
  partial: "bg-[#d97706]/10 text-[#b45309] border-[#d97706]/25",
  failed: "bg-[#dc2626]/10 text-[#b91c1c] border-[#dc2626]/25",
  no_evidence: "bg-muted/40 text-muted-foreground border-border",
};

const scoreColor = (score: number) =>
  score >= 70 ? "#16a34a" : score >= 40 ? "#d97706" : "#dc2626";

interface DomainScoresChartProps {
  domainScores?: DomainScore[];
}

/**
 * One stacked composition bar per domain: how many controls passed /
 * partially passed / failed / lacked evidence. Segment widths are
 * proportional to counts, with 2px surface gaps between fills; the
 * chips underneath double as the legend and the direct labels.
 */
export function DomainScoresChart({ domainScores }: DomainScoresChartProps) {
  if (!domainScores || domainScores.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <BarChart3 className="h-5 w-5" />
          Domain Scores
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-5">
          {domainScores.map((domain) => {
            const total = domain.total_controls || 1;
            return (
              <div key={domain.domain} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{domain.domain}</span>
                  <span className="tabular-nums font-semibold" style={{ color: scoreColor(domain.score) }}>
                    {domain.score}
                    <span className="font-normal text-muted-foreground/60">/100</span>
                  </span>
                </div>

                {/* Stacked composition bar: 2px gaps between segments */}
                <div
                  className="flex h-3 rounded-full overflow-hidden bg-muted gap-[2px]"
                  role="img"
                  aria-label={`${domain.domain}: ${domain.passed} passed, ${domain.partial} partial, ${domain.failed} failed, ${domain.no_evidence} without evidence, of ${total} controls`}
                >
                  {SEGMENTS.map(({ key, color, label }) => {
                    const count = domain[key];
                    if (!count) return null;
                    return (
                      <div
                        key={key}
                        className="h-full first:rounded-l-full last:rounded-r-full transition-all duration-500"
                        style={{
                          width: `${(count / total) * 100}%`,
                          backgroundColor: color,
                          opacity: key === "no_evidence" ? 0.55 : 1,
                        }}
                        title={`${label}: ${count} of ${total} controls`}
                      />
                    );
                  })}
                </div>

                {/* Count chips — the legend and direct labels in one */}
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                  {SEGMENTS.map(({ key, label, icon: Icon }) => {
                    const count = domain[key];
                    if (!count && key !== "passed") return null;
                    return (
                      <span
                        key={key}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${
                          count ? CHIP_STYLES[key] : "bg-muted/40 text-muted-foreground border-border"
                        }`}
                      >
                        <Icon className="h-3 w-3" />
                        {count} {label.toLowerCase()}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
