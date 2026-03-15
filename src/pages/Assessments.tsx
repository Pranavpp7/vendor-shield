import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAssessments } from "@/context/AssessmentContext";
import { RiskBadge } from "@/components/assessment/RiskBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Plus, Search, Eye, Trash2, FileEdit, SortAsc, SortDesc, RotateCcw, Loader2,
} from "lucide-react";
import { motion } from "framer-motion";
import { Skeleton } from "@/components/ui/skeleton";
import { checklistSchema } from "@/data/checklistSchema";
import { generateChecklistFromAI } from "@/lib/api";
import { saveRunSnapshot } from "@/lib/runHistory";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

type SortKey = "vendorName" | "score" | "createdAt";

export default function Assessments() {
  const navigate = useNavigate();
  const { assessments, loading, updateAssessment, deleteAssessment } = useAssessments();
  const { user } = useAuth();
  const [rerunningId, setRerunningId] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("createdAt");
  const [sortAsc, setSortAsc] = useState(false);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((p) => !p);
    else { setSortKey(key); setSortAsc(true); }
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
      if (user) {
        await saveRunSnapshot(id, user.id, result.score, result.riskLevel, result.controls);
      }
      toast.success(`Re-run complete for ${assessment.vendorName}`);
    } catch {
      toast.error("Failed to re-run assessment.");
    } finally {
      setRerunningId(null);
    }
  };

  const filtered = useMemo(() => {
    let list = [...assessments];

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((a) => a.vendorName.toLowerCase().includes(q));
    }
    if (statusFilter !== "all") list = list.filter((a) => a.status === statusFilter);
    if (riskFilter !== "all") list = list.filter((a) => a.riskLevel === riskFilter);

    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "vendorName") cmp = a.vendorName.localeCompare(b.vendorName);
      else if (sortKey === "score") cmp = a.score - b.score;
      else cmp = a.createdAt.localeCompare(b.createdAt);
      return sortAsc ? cmp : -cmp;
    });

    return list;
  }, [assessments, search, statusFilter, riskFilter, sortKey, sortAsc]);

  const statusCounts = useMemo(() => {
    const counts = { all: assessments.length, Draft: 0, Running: 0, Completed: 0 };
    assessments.forEach((a) => counts[a.status]++);
    return counts;
  }, [assessments]);

  const SortIcon = ({ col }: { col: SortKey }) =>
    sortKey === col ? (sortAsc ? <SortAsc className="h-3 w-3 ml-1 inline" /> : <SortDesc className="h-3 w-3 ml-1 inline" />) : null;

  const statusBadge = (status: string) => {
    const cls =
      status === "Completed" ? "bg-risk-low-bg text-risk-low" :
      status === "Running" ? "bg-risk-medium-bg text-risk-medium" :
      "bg-muted text-muted-foreground";
    return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>{status}</span>;
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Assessments</h1>
            <p className="text-muted-foreground mt-1">Manage and track all vendor assessments</p>
          </div>
          <Button onClick={() => navigate("/assessment/new")} className="shadow-md">
            <Plus className="h-4 w-4 mr-2" />
            New Assessment
          </Button>
        </div>

        {/* Status Tabs */}
        <Tabs value={statusFilter} onValueChange={setStatusFilter}>
          <TabsList>
            <TabsTrigger value="all">All ({statusCounts.all})</TabsTrigger>
            <TabsTrigger value="Draft">Drafts ({statusCounts.Draft})</TabsTrigger>
            <TabsTrigger value="Running">Running ({statusCounts.Running})</TabsTrigger>
            <TabsTrigger value="Completed">Completed ({statusCounts.Completed})</TabsTrigger>
          </TabsList>
        </Tabs>

        {/* Search + Filters Row */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search vendors…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={riskFilter} onValueChange={setRiskFilter}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Risk Level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Risks</SelectItem>
              <SelectItem value="Low">Low</SelectItem>
              <SelectItem value="Medium">Medium</SelectItem>
              <SelectItem value="High">High</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="shadow-sm">
            <CardContent className="p-0">
              {loading ? (
                <div className="space-y-3 p-6">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="flex items-center gap-4">
                      <Skeleton className="h-4 flex-1" />
                      <Skeleton className="h-4 w-20" />
                      <Skeleton className="h-4 w-16" />
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
                    <TableHead className="cursor-pointer select-none" onClick={() => toggleSort("vendorName")}>
                      Vendor <SortIcon col="vendorName" />
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Criticality</TableHead>
                    <TableHead className="cursor-pointer select-none" onClick={() => toggleSort("score")}>
                      Score <SortIcon col="score" />
                    </TableHead>
                    <TableHead>Risk Level</TableHead>
                    <TableHead className="cursor-pointer select-none" onClick={() => toggleSort("createdAt")}>
                      Date <SortIcon col="createdAt" />
                    </TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((a) => (
                    <TableRow key={a.id} className="group">
                      <TableCell className="font-medium">{a.vendorName}</TableCell>
                      <TableCell>{statusBadge(a.status)}</TableCell>
                      <TableCell>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          a.criticality === "High" ? "bg-risk-high-bg text-risk-high" :
                          a.criticality === "Medium" ? "bg-risk-medium-bg text-risk-medium" :
                          "bg-risk-low-bg text-risk-low"
                        }`}>{a.criticality}</span>
                      </TableCell>
                      <TableCell className="font-semibold">
                        {a.status === "Draft" ? "—" : `${a.score}/100`}
                      </TableCell>
                      <TableCell>
                        {a.status === "Draft" ? <span className="text-xs text-muted-foreground">N/A</span> : <RiskBadge level={a.riskLevel} />}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{a.createdAt}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          {a.status === "Draft" ? (
                            <Button variant="ghost" size="sm" onClick={() => navigate(`/assessment/new?draft=${a.id}`)}>
                              <FileEdit className="h-4 w-4 mr-1" />
                              Continue
                            </Button>
                          ) : (
                            <Button variant="ghost" size="sm" onClick={() => navigate(`/assessments/${a.id}`)}>
                              <Eye className="h-4 w-4 mr-1" />
                              View
                            </Button>
                          )}
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
                                variant="ghost" size="sm"
                                className="text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Permanently Delete Assessment</AlertDialogTitle>
                                <AlertDialogDescription>
                                  This will permanently delete the assessment for <strong>{a.vendorName}</strong>, including all uploaded documents, indexed data, and run history. This action cannot be undone.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() => deleteAssessment(a.id)}
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                >
                                  Delete Permanently
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
                      <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                        {search ? "No assessments match your search" : "No assessments yet"}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </AppLayout>
  );
}
