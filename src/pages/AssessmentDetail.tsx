import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAssessments } from "@/context/AssessmentContext";
import { RiskBadge } from "@/components/assessment/RiskBadge";
import { ChecklistSection } from "@/components/assessment/ChecklistSection";
import { ChatPanel } from "@/components/assessment/ChatPanel";
import { SummaryModal } from "@/components/assessment/SummaryModal";
import { DocsLinksSection } from "@/components/assessment/DocsLinksSection";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ArrowLeft, FileText, AlertCircle, Loader2, Info, History, AlertTriangle, XCircle, TrendingUp } from "lucide-react";
import { ChatMessage, Assessment } from "@/types/assessment";
import { useChecklistSchema } from "@/hooks/useChecklistSchema";
import { generateChecklistFromAI, fetchAssessmentDetail } from "@/lib/api";
import { toast } from "sonner";
import { RunHistoryPanel } from "@/components/assessment/RunHistoryPanel";
import { VendorTrendView } from "@/components/assessment/VendorTrendView";
import { DomainScoresChart } from "@/components/assessment/DomainScoresChart";
import { SendReportButton } from "@/components/SendReportButton";

export default function AssessmentDetail() {
  const { vendorSlug } = useParams();
  const navigate = useNavigate();
  const { getAssessmentBySlug, updateAssessment } = useAssessments();
  const [summaryOpen, setSummaryOpen] = useState(false);
  const { allControls: checklistAllControls } = useChecklistSchema();
  const [rerunning, setRerunning] = useState(false);
  const [activeTab, setActiveTab] = useState("checklist");
  const [highlightDoc, setHighlightDoc] = useState<string | null>(null);
  const [docsStillIndexing, setDocsStillIndexing] = useState(false);

  const contextAssessment = getAssessmentBySlug(vendorSlug || "");
  const [detailAssessment, setDetailAssessment] = useState<Assessment | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    if (!vendorSlug) return;
    console.log("[AssessmentDetail] fetching detail for id:", vendorSlug);
    setDetailLoading(true);
    fetchAssessmentDetail(vendorSlug)
      .then((data) => {
        setDetailAssessment(data);
        setDetailError(null);
      })
      .catch((err) => {
        console.error("fetchAssessmentDetail failed:", err);
        setDetailError(err.message || "Failed to load latest assessment data");
      })
      .finally(() => setDetailLoading(false));
  }, [vendorSlug]);

  const assessment = detailAssessment ?? contextAssessment;

  // Local notes state with 1-second debounce to avoid API calls on every keystroke
  const [notesValue, setNotesValue] = useState(assessment?.notes ?? "");
  const notesSaveTimer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    setNotesValue(assessment?.notes ?? "");
  }, [assessment?.id]);

  const handleNotesChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setNotesValue(value);
    clearTimeout(notesSaveTimer.current);
    notesSaveTimer.current = setTimeout(() => {
      if (assessment) updateAssessment(assessment.id, { notes: value });
    }, 1000);
  };

  useEffect(() => { setDocsStillIndexing(false); }, []);

  const handleRerunChecklist = async () => {
    if (!assessment) return;
    setRerunning(true);
    try {
      const result = await generateChecklistFromAI(assessment.vendorName, checklistAllControls, assessment.id);
      updateAssessment(assessment.id, {
        controls: result.controls,
        score: result.score,
        riskLevel: result.riskLevel as "Low" | "Medium" | "High",
        domainScores: result.domainScores,
        gapsSummary: result.gapsSummary,
      });
      toast.success("Checklist re-run complete with latest document data.");
    } catch {
      toast.error("Failed to re-run checklist.");
    } finally {
      setRerunning(false);
    }
  };


  if (detailLoading && !assessment) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </AppLayout>
    );
  }

  if (!assessment) {
    return (
      <AppLayout>
        <div className="text-center py-16">
          <p className="text-muted-foreground">Assessment not found.</p>
          <Button variant="outline" className="mt-4" onClick={() => navigate("/dashboard")}>
            Back to Dashboard
          </Button>
        </div>
      </AppLayout>
    );
  }

  const passedCount = assessment.controls.filter((c) => c.status === "passed").length;
  const failedCount = assessment.controls.filter((c) => c.status === "failed").length;
  const needsInfoCount = assessment.controls.filter((c) => c.status === "needs_info").length;

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate("/dashboard")}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold">{assessment.vendorName}</h1>
              <div className="flex items-center gap-3 mt-1 flex-wrap">
                <RiskBadge level={assessment.riskLevel} />
                <span className="text-sm text-muted-foreground">
                  Criticality: {assessment.criticality}
                </span>
                <span className="text-sm text-muted-foreground">
                  Date: {assessment.createdAt}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-3xl font-bold">{assessment.score}</p>
              <p className="text-xs text-muted-foreground">/ 100</p>
            </div>
            <Button variant="outline" onClick={() => setSummaryOpen(true)}>
              <FileText className="h-4 w-4 mr-2" />
              Summary
            </Button>
            <SendReportButton
              assessmentId={assessment.id}
              vendorName={assessment.vendorName}
            />
          </div>
        </div>

        {detailError && (
          <div className="text-xs text-yellow-600 bg-yellow-50 border border-yellow-200 rounded px-3 py-2">
            ⚠ Showing cached data — could not load latest results ({detailError})
          </div>
        )}

        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold">{assessment.controls.length}</p>
              <p className="text-xs text-muted-foreground">Total Controls</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-risk-low">{passedCount}</p>
              <p className="text-xs text-muted-foreground">Passed</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-risk-high">{failedCount}</p>
              <p className="text-xs text-muted-foreground">Failed</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-amber-500">{needsInfoCount}</p>
              <p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
                <AlertCircle className="h-3 w-3" /> Needs Info
              </p>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="checklist">Checklist</TabsTrigger>
            <TabsTrigger value="docs" data-value="docs">Documents & Links</TabsTrigger>
            <TabsTrigger value="chat">Chat & Insights</TabsTrigger>
            <TabsTrigger value="notes">Notes</TabsTrigger>
            <TabsTrigger value="history">
              <History className="h-3.5 w-3.5 mr-1.5" />
              History
            </TabsTrigger>
            <TabsTrigger value="trend">
              <TrendingUp className="h-3.5 w-3.5 mr-1.5" />
              Trend
            </TabsTrigger>
          </TabsList>

          <TabsContent value="checklist">
            <div className="space-y-4">
              {assessment.error && (
                <Card className="border-red-500/30 bg-red-500/5">
                  <CardContent className="pt-4 pb-4 flex items-center gap-3">
                    <XCircle className="h-4 w-4 text-red-500 shrink-0" />
                    <p className="text-sm">{assessment.error}</p>
                  </CardContent>
                </Card>
              )}
              {assessment.warning && (
                <Card className="border-amber-500/30 bg-amber-500/5">
                  <CardContent className="pt-4 pb-4 flex items-center gap-3">
                    <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                    <p className="text-sm">{assessment.warning}</p>
                  </CardContent>
                </Card>
              )}
              <DomainScoresChart domainScores={assessment.domainScores} />
              
              {docsStillIndexing && (
                <Card className="border-accent/30 bg-accent/5">
                  <CardContent className="pt-4 pb-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Loader2 className="h-4 w-4 animate-spin text-accent" />
                      <p className="text-sm">Documents are still being indexed. Re-run the checklist once indexing completes for accurate results.</p>
                    </div>
                  </CardContent>
                </Card>
              )}
              {!docsStillIndexing && assessment.controls.length > 0 && assessment.controls.every(c => c.status === "needs_info") && (
                <Card className="border-amber-500/30 bg-amber-500/5">
                  <CardContent className="pt-4 pb-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Info className="h-4 w-4 text-amber-500" />
                      <p className="text-sm">All controls show "Needs Info". If you've uploaded documents, try re-running the checklist to incorporate them.</p>
                    </div>
                    <Button size="sm" variant="outline" onClick={handleRerunChecklist} disabled={rerunning}>
                      {rerunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Re-run Now"}
                    </Button>
                  </CardContent>
                </Card>
              )}
              <Card>
                <CardContent className="pt-6">
                  <ChecklistSection
                    controls={assessment.controls}
                    uploadedFiles={assessment.uploadedFiles}
                    links={assessment.links}
                    onNavigateToDocs={(evidenceSource) => {
                      setHighlightDoc(evidenceSource || null);
                      setActiveTab("docs");
                    }}
                    onRerunChecklist={handleRerunChecklist}
                    rerunning={rerunning}
                  />
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="docs">
            {rerunning && (
              <Card className="mb-4 border-accent/30">
                <CardContent className="pt-4 pb-4 flex items-center gap-3">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <p className="text-sm">Re-running checklist with updated documents…</p>
                </CardContent>
              </Card>
            )}
            <DocsLinksSection
              files={assessment.uploadedFiles}
              links={assessment.links}
              onUpdateFiles={(files) => updateAssessment(assessment.id, { uploadedFiles: files })}
              onUpdateLinks={(links) => updateAssessment(assessment.id, { links })}
              assessmentId={assessment.id}
              vendorName={assessment.vendorName}
              onRerunChecklist={handleRerunChecklist}
              highlightDoc={highlightDoc}
              onClearHighlight={() => setHighlightDoc(null)}
            />
          </TabsContent>

          <TabsContent value="chat">
            <Card>
              <CardContent className="pt-6">
                <ChatPanel
                  chatHistory={assessment.chatHistory}
                  checklistJson={JSON.stringify({
                    vendor: assessment.vendorName,
                    score: assessment.score,
                    controls: assessment.controls,
                  })}
                  onNewMessage={(msgs: ChatMessage[]) =>
                    updateAssessment(assessment.id, { chatHistory: msgs })
                  }
                  assessmentId={assessment.id}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="notes">
            <Card>
              <CardHeader>
                <CardTitle>Analyst Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  placeholder="Add your observations, recommendations, or follow-up items here…"
                  value={notesValue}
                  onChange={handleNotesChange}
                  className="min-h-[200px]"
                />
                <p className="text-xs text-muted-foreground mt-2">Changes are auto-saved</p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="history">
            <RunHistoryPanel assessmentId={assessment.id} />
          </TabsContent>

          <TabsContent value="trend">
            <VendorTrendView
              vendorName={assessment.vendorName}
              currentAssessmentId={assessment.id}
            />
          </TabsContent>
        </Tabs>
      </div>

      <SummaryModal
        open={summaryOpen}
        onOpenChange={setSummaryOpen}
        assessment={assessment}
      />
    </AppLayout>
  );
}
