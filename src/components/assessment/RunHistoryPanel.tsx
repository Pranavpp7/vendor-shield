import { useEffect, useState } from "react";
import { fetchRunHistory, RunRecord } from "@/lib/runHistory";
import { RiskBadge } from "./RiskBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts";

type Props = {
  assessmentId: string;
};

const chartConfig = {
  score: {
    label: "Score",
    color: "hsl(var(--accent))",
  },
};

export function RunHistoryPanel({ assessmentId }: Props) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRunHistory(assessmentId).then((data) => {
      setRuns(data);
      setLoading(false);
    });
  }, [assessmentId]);

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6 text-center text-muted-foreground py-12">
          No run history yet. Complete an assessment to see results here.
        </CardContent>
      </Card>
    );
  }

  const chartData = runs.map((r, i) => ({
    run: `Run ${i + 1}`,
    score: r.score,
    date: new Date(r.runAt).toLocaleDateString(),
  }));

  return (
    <div className="space-y-6">
      {runs.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Score Over Time</CardTitle>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[220px] w-full">
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="run" className="text-xs" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} className="text-xs" tick={{ fontSize: 12 }} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="hsl(var(--accent))"
                  strokeWidth={2}
                  dot={{ r: 4, fill: "hsl(var(--accent))" }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run History ({runs.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Passed</TableHead>
                <TableHead>Failed</TableHead>
                <TableHead>Needs Info</TableHead>
                <TableHead>Trend</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...runs].reverse().map((run, idx) => {
                const runNumber = runs.length - idx;
                const prevRun = idx < runs.length - 1 ? runs[runs.length - idx - 2] : null;
                const diff = prevRun ? run.score - prevRun.score : 0;

                return (
                  <TableRow key={run.id}>
                    <TableCell className="font-medium">#{runNumber}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(run.runAt).toLocaleString()}
                    </TableCell>
                    <TableCell className="font-semibold">{run.score}/100</TableCell>
                    <TableCell>
                      <RiskBadge level={run.riskLevel as "Low" | "Medium" | "High"} />
                    </TableCell>
                    <TableCell className="text-risk-low font-medium">{run.passedCount}</TableCell>
                    <TableCell className="text-risk-high font-medium">{run.failedCount}</TableCell>
                    <TableCell className="text-amber-500 font-medium">{run.needsInfoCount}</TableCell>
                    <TableCell>
                      {prevRun ? (
                        <span className={`inline-flex items-center gap-1 text-sm font-medium ${
                          diff > 0 ? "text-risk-low" : diff < 0 ? "text-risk-high" : "text-muted-foreground"
                        }`}>
                          {diff > 0 ? <TrendingUp className="h-3.5 w-3.5" /> : diff < 0 ? <TrendingDown className="h-3.5 w-3.5" /> : <Minus className="h-3.5 w-3.5" />}
                          {diff > 0 ? "+" : ""}{diff}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
