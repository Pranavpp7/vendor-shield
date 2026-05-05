import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Activity, Upload, FileSearch, Layers, Brain, CheckCircle, Loader2, XCircle } from "lucide-react";
import { motion } from "framer-motion";
import { fetchDocuments } from "@/lib/api";

type PipelineStage = {
  id: string;
  label: string;
  icon: React.ReactNode;
  status: "pending" | "active" | "done" | "error";
};

type Props = {
  assessmentId: string;
  documents: { id: string; file_name: string; status: string }[];
};

function getStagesForDoc(docStatus: string): PipelineStage[] {
  const stages: PipelineStage[] = [
    { id: "upload", label: "Uploaded", icon: <Upload className="h-4 w-4" />, status: "done" },
    { id: "parse", label: "Text Extraction", icon: <FileSearch className="h-4 w-4" />, status: "pending" },
    { id: "chunk", label: "Chunking", icon: <Layers className="h-4 w-4" />, status: "pending" },
    { id: "embed", label: "Embedding", icon: <Brain className="h-4 w-4" />, status: "pending" },
    { id: "ready", label: "Indexed", icon: <CheckCircle className="h-4 w-4" />, status: "pending" },
  ];

  if (docStatus === "pending") {
    stages[1].status = "active";
  } else if (docStatus === "processing") {
    stages[1].status = "done";
    stages[2].status = "done";
    stages[3].status = "active";
  } else if (docStatus === "ready") {
    stages[1].status = "done";
    stages[2].status = "done";
    stages[3].status = "done";
    stages[4].status = "done";
  } else if (docStatus === "error") {
    stages[1].status = "error";
  }

  return stages;
}

function StageNode({ stage, isLast }: { stage: PipelineStage; isLast: boolean }) {
  const colorMap = {
    pending: "text-muted-foreground border-border bg-muted/30",
    active: "text-amber-500 border-amber-500/50 bg-amber-500/10",
    done: "text-risk-low border-risk-low/50 bg-risk-low/10",
    error: "text-risk-high border-risk-high/50 bg-risk-high/10",
  };

  const lineColor = {
    pending: "bg-border",
    active: "bg-amber-500/40",
    done: "bg-risk-low/50",
    error: "bg-risk-high/50",
  };

  return (
    <div className="flex items-center gap-0">
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className={`flex flex-col items-center gap-1.5`}
      >
        <div className={`h-9 w-9 rounded-full border-2 flex items-center justify-center ${colorMap[stage.status]}`}>
          {stage.status === "active" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : stage.status === "error" ? (
            <XCircle className="h-4 w-4" />
          ) : (
            stage.icon
          )}
        </div>
        <span className={`text-[10px] font-medium whitespace-nowrap ${
          stage.status === "done" ? "text-risk-low" :
          stage.status === "active" ? "text-amber-500" :
          stage.status === "error" ? "text-risk-high" :
          "text-muted-foreground"
        }`}>
          {stage.label}
        </span>
      </motion.div>
      {!isLast && (
        <div className={`h-0.5 w-8 mx-1 rounded-full mt-[-18px] ${lineColor[stage.status]}`} />
      )}
    </div>
  );
}

export function IndexingPipelineFlow({ assessmentId, documents }: Props) {
  const [open, setOpen] = useState(false);
  const [liveDocuments, setLiveDocuments] = useState(documents);

  useEffect(() => {
    setLiveDocuments(documents);
  }, [documents]);

  useEffect(() => {
    if (!open) return;
    const processing = liveDocuments.some(d => d.status === "pending" || d.status === "processing");
    if (!processing) return;

    const interval = setInterval(async () => {
      try {
        const docs = await fetchDocuments(assessmentId);
        setLiveDocuments(docs);
      } catch {
        // keep current view when polling fails
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [open, liveDocuments, assessmentId]);

  if (documents.length === 0) return null;

  const processing = liveDocuments.some(d => d.status === "pending" || d.status === "processing");

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        className="gap-1.5"
      >
        <Activity className={`h-3.5 w-3.5 ${processing ? "animate-pulse text-amber-500" : ""}`} />
        Indexing Pipeline
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Document Indexing Pipeline
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
            {liveDocuments.map((doc) => {
              const stages = getStagesForDoc(doc.status);
              return (
                <div key={doc.id} className="rounded-lg border bg-card p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium truncate flex-1">{doc.file_name}</p>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                      doc.status === "ready" ? "bg-risk-low/10 text-risk-low" :
                      doc.status === "error" ? "bg-risk-high/10 text-risk-high" :
                      "bg-amber-500/10 text-amber-500"
                    }`}>
                      {doc.status}
                    </span>
                  </div>
                  <div className="flex items-start justify-center gap-0 py-2">
                    {stages.map((stage, i) => (
                      <StageNode key={stage.id} stage={stage} isLast={i === stages.length - 1} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {processing && (
            <p className="text-xs text-muted-foreground text-center animate-pulse">
              Pipeline is running… auto-refreshing every 2 seconds
            </p>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
