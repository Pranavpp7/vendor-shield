import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DomainScore } from "@/types/assessment";
import { BarChart3, CheckCircle2, MinusCircle, XCircle, HelpCircle } from "lucide-react";

interface DomainScoresChartProps {
  domainScores?: DomainScore[];
}

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
          {domainScores.map((domain) => (
            <div key={domain.domain} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{domain.domain}</span>
                <span className="tabular-nums font-semibold text-muted-foreground">
                  {domain.score}
                  <span className="font-normal text-muted-foreground/60">/100</span>
                </span>
              </div>

              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    domain.score >= 70
                      ? "bg-emerald-500"
                      : domain.score >= 40
                      ? "bg-amber-500"
                      : "bg-red-500"
                  }`}
                  style={{ width: `${domain.score}%` }}
                />
              </div>

              <div className="flex flex-wrap gap-1.5 pt-0.5">
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${
                  domain.passed > 0
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-muted/40 text-muted-foreground border-border"
                }`}>
                  <CheckCircle2 className="h-3 w-3" />
                  {domain.passed} passed
                </span>

                {domain.partial > 0 && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border bg-orange-50 text-orange-700 border-orange-200">
                    <MinusCircle className="h-3 w-3" />
                    {domain.partial} partial
                  </span>
                )}

                {domain.failed > 0 && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border bg-red-50 text-red-700 border-red-200">
                    <XCircle className="h-3 w-3" />
                    {domain.failed} failed
                  </span>
                )}

                {domain.no_evidence > 0 && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border bg-slate-50 text-slate-500 border-slate-200">
                    <HelpCircle className="h-3 w-3" />
                    {domain.no_evidence} no evidence
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
