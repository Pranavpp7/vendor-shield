import { useState, useEffect } from "react";
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
import { ArrowLeft, FileText, AlertCircle, Loader2, Info } from "lucide-react";
import { ChatMessage } from "@/types/assessment";
import { checklistSchema } from "@/data/checklistSchema";
import { generateChecklistFromAI } from "@/lib/api";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";

export default function AssessmentDetail() {
  const { vendorSlug } = useParams();
  const navigate = useNavigate();
  const { getAssessmentBySlug, updateAssessment } = useAssessments();
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [activeTab, setActiveTab] = useState("checklist");
  const [highlightDoc, setHighlightDoc] = useState<string | null>(null);
  const [docsStillIndexing, setDocsStillIndexing] = useState(false);

  const assessment = getAssessmentBySlug(vendorSlug || "");

  // Check if any documents are still being indexed
  useEffect(() => {
    if (!assessment) return;
    const checkIndexing = async () => {
      const { data: docs } = await supabase
        .from("documents")
        .select("id, status")
        .eq("assessment_id", assessment.id);
      if (docs && docs.length > 0) {
        const pending = docs.filter((d) => d.status !== "ready" && d.status !== "error");
        setDocsStillIndexing(pending.length > 0);
      }
    };
    checkIndexing();
    const interval = setInterval(checkIndexing, 5000);
    return () => clearInterval(interval);
  }, [assessment?.id]);

  const handleRerunChecklist = async () => {
    if (!assessment) return;
    setRerunning(true);
    try {
      const allControls = checklistSchema.flatMap((g) =>
        g.controls.map((c) => ({ id: c.id, category: g.category, name: c.name }))
      );
      const result = await generateChecklistFromAI(assessment.vendorName, allControls, assessment.id);
      updateAssessment(assessment.id, {
        controls: result.controls,
        score: result.score,
        riskLevel: result.riskLevel as "Low" | "Medium" | "High",
      });
      toast.success("Checklist re-run complete with latest document data.");
    } catch {
      toast.error("Failed to re-run checklist.");
    } finally {
      setRerunning(false);
    }
  };


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
          </div>
        </div>

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
          </TabsList>

          <TabsContent value="checklist">
            {docsStillIndexing && (
              <Card className="mb-4 border-accent/30 bg-accent/5">
                <CardContent className="pt-4 pb-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Loader2 className="h-4 w-4 animate-spin text-accent" />
                    <p className="text-sm">Documents are still being indexed. Re-run the checklist once indexing completes for accurate results.</p>
                  </div>
                </CardContent>
              </Card>
            )}
            {!docsStillIndexing && assessment.controls.length > 0 && assessment.controls.every(c => c.status === "needs_info") && (
              <Card className="mb-4 border-amber-500/30 bg-amber-500/5">
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
                  value={assessment.notes}
                  onChange={(e) =>
                    updateAssessment(assessment.id, { notes: e.target.value })
                  }
                  className="min-h-[200px]"
                />
                <p className="text-xs text-muted-foreground mt-2">Changes are auto-saved</p>
              </CardContent>
            </Card>
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
