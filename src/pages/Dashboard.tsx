import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAssessments } from "@/context/AssessmentContext";
import { RiskBadge } from "@/components/assessment/RiskBadge";
import { CompareModal } from "@/components/assessment/CompareModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Plus, GitCompare, Eye, Shield, AlertTriangle, CheckCircle } from "lucide-react";

export default function Dashboard() {
  const navigate = useNavigate();
  const { assessments } = useAssessments();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [compareOpen, setCompareOpen] = useState(false);

  const filtered =
    riskFilter === "all"
      ? assessments
      : assessments.filter((a) => a.riskLevel === riskFilter);

  const highRisk = assessments.filter((a) => a.riskLevel === "High").length;
  const avgScore = assessments.length
    ? Math.round(assessments.reduce((s, a) => s + a.score, 0) / assessments.length)
    : 0;

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <AppLayout>
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground mt-1">Overview of vendor risk assessments</p>
          </div>
          <Button onClick={() => navigate("/assessment/new")}>
            <Plus className="h-4 w-4 mr-2" />
            New Assessment
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-secondary">
                  <Shield className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{assessments.length}</p>
                  <p className="text-xs text-muted-foreground">Total Vendors</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-risk-high-bg">
                  <AlertTriangle className="h-5 w-5 text-risk-high" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{highRisk}</p>
                  <p className="text-xs text-muted-foreground">High Risk</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-risk-low-bg">
                  <CheckCircle className="h-5 w-5 text-risk-low" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{avgScore}</p>
                  <p className="text-xs text-muted-foreground">Avg Score</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Recent Assessments</CardTitle>
              <div className="flex items-center gap-2">
                <Select value={riskFilter} onValueChange={setRiskFilter}>
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Filter by risk" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Levels</SelectItem>
                    <SelectItem value="Low">Low</SelectItem>
                    <SelectItem value="Medium">Medium</SelectItem>
                    <SelectItem value="High">High</SelectItem>
                  </SelectContent>
                </Select>
                {selectedIds.length >= 2 && (
                  <Button variant="outline" size="sm" onClick={() => setCompareOpen(true)}>
                    <GitCompare className="h-4 w-4 mr-2" />
                    Compare ({selectedIds.length})
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40px]"></TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Risk Level</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.includes(a.id)}
                        onCheckedChange={() => toggleSelect(a.id)}
                      />
                    </TableCell>
                    <TableCell className="font-medium">{a.vendorName}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          a.status === "Completed"
                            ? "bg-risk-low-bg text-risk-low"
                            : "bg-risk-medium-bg text-risk-medium"
                        }`}
                      >
                        {a.status}
                      </span>
                    </TableCell>
                    <TableCell className="font-semibold">{a.score}/100</TableCell>
                    <TableCell>
                      <RiskBadge level={a.riskLevel} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">{a.createdAt}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/assessment/${a.id}`)}
                      >
                        <Eye className="h-4 w-4 mr-1" />
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {filtered.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                      No assessments found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <CompareModal
        open={compareOpen}
        onOpenChange={setCompareOpen}
        assessments={assessments.filter((a) => selectedIds.includes(a.id))}
      />
    </AppLayout>
  );
}
