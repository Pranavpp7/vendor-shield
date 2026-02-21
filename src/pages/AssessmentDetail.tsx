import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAssessments } from "@/context/AssessmentContext";
import { RiskBadge } from "@/components/assessment/RiskBadge";
import { ChecklistSection } from "@/components/assessment/ChecklistSection";
import { ChatPanel } from "@/components/assessment/ChatPanel";
import { SummaryModal } from "@/components/assessment/SummaryModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ArrowLeft, FileText } from "lucide-react";
import { ChatMessage } from "@/types/assessment";

export default function AssessmentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { getAssessment, updateAssessment } = useAssessments();
  const [summaryOpen, setSummaryOpen] = useState(false);

  const assessment = getAssessment(id || "");

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

  const passedCount = assessment.controls.filter((c) => c.passed).length;
  const failedCount = assessment.controls.filter((c) => !c.passed).length;

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

        <div className="grid grid-cols-3 gap-4">
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
        </div>

        <Tabs defaultValue="checklist" className="space-y-4">
          <TabsList>
            <TabsTrigger value="checklist">Checklist</TabsTrigger>
            <TabsTrigger value="chat">Chat & Insights</TabsTrigger>
            <TabsTrigger value="notes">Notes</TabsTrigger>
          </TabsList>

          <TabsContent value="checklist">
            <Card>
              <CardContent className="pt-6">
                <ChecklistSection controls={assessment.controls} />
              </CardContent>
            </Card>
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
