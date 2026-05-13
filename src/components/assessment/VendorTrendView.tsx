import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TrendingUp, ArrowLeftRight, Loader2, Info } from "lucide-react";
import { fetchVendorHistory, VendorHistoryEntry } from "@/lib/api";

const OVERALL_COLOR = "#1e3a5f";
const DOMAIN_PALETTE = ["#2563eb", "#16a34a", "#ea580c", "#9333ea", "#dc2626", "#06b6d4"];

type Props = {
  vendorName: string;
  currentAssessmentId: string;
};

export function VendorTrendView({ vendorName, currentAssessmentId }: Props) {
  const navigate = useNavigate();
  const [history, setHistory] = useState<VendorHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchVendorHistory(vendorName)
      .then((data) => {
        if (!cancelled) setHistory(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load history");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [vendorName]);

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6 flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading vendor history…
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-destructive">
          {error}
        </CardContent>
      </Card>
    );
  }

  // Single-assessment state — nothing to chart yet
  if (history.length <= 1) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" /> Score trend
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-3 text-sm text-muted-foreground">
          <Info className="h-4 w-4 shrink-0" />
          <p>Run another assessment after vendor updates to track improvement.</p>
        </CardContent>
      </Card>
    );
  }

  // Build chart rows + a stable list of domain names from all entries
  const allDomains = new Set<string>();
  history.forEach((h) =>
    Object.keys(h.domain_scores || {}).forEach((d) => allDomains.add(d))
  );
  const domainList = Array.from(allDomains);

  const chartData = history.map((h) => {
    const point: Record<string, string | number> = {
      date: new Date(h.created_at).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      }),
      Overall: h.score,
    };
    for (const d of domainList) {
      const v = h.domain_scores?.[d];
      if (typeof v === "number") point[d] = v;
    }
    return point;
  });

  const previousId =
    history.length >= 2
      ? history[history.length - 2].id
      : history[0].id;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" /> Score trend across {history.length} assessments
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              navigate(`/compare?ids=${previousId},${currentAssessmentId}`)
            }
          >
            <ArrowLeftRight className="h-3.5 w-3.5 mr-1.5" />
            Compare with previous
          </Button>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="Overall"
                stroke={OVERALL_COLOR}
                strokeWidth={3}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
              {domainList.map((d, i) => (
                <Line
                  key={d}
                  type="monotone"
                  dataKey={d}
                  stroke={DOMAIN_PALETTE[i % DOMAIN_PALETTE.length]}
                  strokeWidth={1.5}
                  dot={{ r: 3 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Past assessments</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...history].reverse().map((h) => (
                <TableRow key={h.id}>
                  <TableCell>
                    {new Date(h.created_at).toLocaleString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </TableCell>
                  <TableCell className="text-right font-mono">{h.score}/100</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {h.id === currentAssessmentId ? "current" : ""}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
