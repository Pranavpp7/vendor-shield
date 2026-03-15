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
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Plus, GitCompare, Eye, Shield, AlertTriangle, CheckCircle, Trash2, TrendingUp, RotateCcw, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { Skeleton } from "@/components/ui/skeleton";
import { checklistSchema } from "@/data/checklistSchema";
import { generateChecklistFromAI } from "@/lib/api";
import { saveRunSnapshot } from "@/lib/runHistory";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

export default function Dashboard() {
  const navigate = useNavigate();
  const { assessments, loading, updateAssessment, deleteAssessment } = useAssessments();
  const [rerunningId, setRerunningId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [compareOpen, setCompareOpen] = useState(false);

  const filtered =
    riskFilter === "all"
      ? assessments
      : assessments.filter((a) => a.riskLevel === riskFilter);

  const highRisk = assessments.filter((a) => a.riskLevel === "High").length;
  const lowRisk = assessments.filter((a) => a.riskLevel === "Low").length;
  const avgScore = assessments.length
    ? Math.round(assessments.reduce((s, a) => s + a.score, 0) / assessments.length)
    : 0;

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleDelete = (id: string) => {
    deleteAssessment(id);
    setSelectedIds((prev) => prev.filter((x) => x !== id));
  };

  const handleRerun = async (id: string) => {
    const assessment = assessments.find((a) => a.id === id);
    if (!assessment) return;
    setRerunningId(id);
    try {
      await updateAssessment(id, { status: "Running" });
      const allControls = checklistSchema.flatMap((g) =>
        g.controls.map((c) => ({ id: c.id, category: g.category, name: c.name }))
      );
      const result = await generateChecklistFromAI(assessment.vendorName, allControls, id);
      await updateAssessment(id, {
        controls: result.controls,
        score: result.score,
        riskLevel: result.riskLevel as "Low" | "Medium" | "High",
        status: "Completed",
      });
      toast.success(`Re-run complete for ${assessment.vendorName}`);
    } catch {
      toast.error("Failed to re-run assessment.");
    } finally {
      setRerunningId(null);
    }
  };

  const statCards = [
    { icon: Shield, label: "Total Vendors", value: assessments.length, bgClass: "bg-secondary", iconClass: "text-accent" },
    { icon: AlertTriangle, label: "High Risk", value: highRisk, bgClass: "bg-risk-high-bg", iconClass: "text-risk-high" },
    { icon: CheckCircle, label: "Low Risk", value: lowRisk, bgClass: "bg-risk-low-bg", iconClass: "text-risk-low" },
    { icon: TrendingUp, label: "Avg Score", value: avgScore, bgClass: "bg-accent/10", iconClass: "text-accent" },
  ];

  return (
    <AppLayout>
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground mt-1">Overview of vendor risk assessments</p>
          </div>
          <Button onClick={() => navigate("/assessment/new")} className="shadow-md">
            <Plus className="h-4 w-4 mr-2" />
            New Assessment
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
            >
              <Card className="hover:shadow-lg transition-shadow">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-xl ${stat.bgClass}`}>
                      <stat.icon className={`h-5 w-5 ${stat.iconClass}`} />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{stat.value}</p>
                      <p className="text-xs text-muted-foreground">{stat.label}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        <Card className="shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-3">
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
            {loading ? (
              <div className="space-y-3 py-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-4 w-4 rounded" />
                    <Skeleton className="h-4 flex-1" />
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 w-16" />
                    <Skeleton className="h-4 w-16" />
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-16" />
                  </div>
                ))}
              </div>
            ) : (
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
                  <TableRow key={a.id} className="group">
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.includes(a.id)}
                        onCheckedChange={() => toggleSelect(a.id)}
                      />
                    </TableCell>
                    <TableCell className="font-medium">{a.vendorName}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
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
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/assessments/${a.id}`)}
                        >
                          <Eye className="h-4 w-4 mr-1" />
                          View
                        </Button>
                        {a.status === "Completed" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={rerunningId === a.id}
                            onClick={() => handleRerun(a.id)}
                            className="text-muted-foreground hover:text-accent"
                          >
                            {rerunningId === a.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <RotateCcw className="h-4 w-4" />
                            )}
                          </Button>
                        )}
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Assessment</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to delete the assessment for <strong>{a.vendorName}</strong>? This action cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleDelete(a.id)}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              >
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
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
            )}
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
