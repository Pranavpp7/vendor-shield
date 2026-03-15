import { useState } from "react";
import { ControlResult, UploadedFile } from "@/types/assessment";
import { Check, X, AlertCircle, Loader2, ChevronDown, ChevronUp, Sparkles, FileText, ExternalLink, RefreshCw, Globe } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";

type Props = {
  controls: ControlResult[];
  isRunning?: boolean;
  revealedCount?: number;
  uploadedFiles?: UploadedFile[];
  links?: string[];
  onNavigateToDocs?: (evidenceSource?: string) => void;
  onRerunChecklist?: () => void;
  rerunning?: boolean;
};

function StatusIcon({ status }: { status: ControlResult["status"] }) {
  if (status === "passed") {
    return (
      <div className="h-5 w-5 rounded-full bg-risk-low-bg flex items-center justify-center flex-shrink-0">
        <Check className="h-3 w-3 text-risk-low" />
      </div>
    );
  }
  if (status === "needs_info") {
    return (
      <div className="h-5 w-5 rounded-full bg-amber-500/15 flex items-center justify-center flex-shrink-0">
        <AlertCircle className="h-3 w-3 text-amber-500" />
      </div>
    );
  }
  return (
    <div className="h-5 w-5 rounded-full bg-risk-high-bg flex items-center justify-center flex-shrink-0">
      <X className="h-3 w-3 text-risk-high" />
    </div>
  );
}

function statusLabel(status: ControlResult["status"]) {
  if (status === "passed") return "Passed";
  if (status === "needs_info") return "Needs Info";
  return "Failed";
}

export function ChecklistSection({ controls, isRunning, revealedCount = controls.length, uploadedFiles = [], links = [], onNavigateToDocs, onRerunChecklist, rerunning }: Props) {
  const categories = [...new Set(controls.map((c) => c.category))];
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {onRerunChecklist && (
        <div className="flex justify-end">
          <Button size="sm" variant="outline" onClick={onRerunChecklist} disabled={rerunning}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${rerunning ? "animate-spin" : ""}`} />
            {rerunning ? "Re-running…" : "Re-run Checklist"}
          </Button>
        </div>
      )}
      {categories.map((category) => {
        const categoryControls = controls.filter((c) => c.category === category);
        return (
          <div key={category}>
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              {category}
            </h3>
            <div className="space-y-2">
              {categoryControls.map((control) => {
                const globalIdx = controls.findIndex((c) => c.id === control.id);
                const isRevealed = globalIdx < revealedCount;
                const isOpen = expanded.has(control.id);

                return (
                  <motion.div
                    key={control.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: globalIdx * 0.08, duration: 0.3 }}
                    className="rounded-lg bg-card border overflow-hidden"
                  >
                    <div
                      className="flex items-center gap-3 p-3 cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => isRevealed && toggle(control.id)}
                    >
                      {!isRevealed ? (
                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                      ) : (
                        <StatusIcon status={control.status} />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium">{control.name}</p>
                        {isRevealed && (
                          <span className={`text-[11px] font-medium ${
                            control.status === "passed" ? "text-risk-low" :
                            control.status === "needs_info" ? "text-amber-500" :
                            "text-risk-high"
                          }`}>
                            {statusLabel(control.status)}
                          </span>
                        )}
                      </div>
                      {isRevealed && (
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <Sparkles className="h-3 w-3" />
                          {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </div>
                      )}
                      {!isRevealed && (
                        <span className="text-xs text-muted-foreground italic">Analyzing…</span>
                      )}
                    </div>
                    <AnimatePresence>
                      {isOpen && isRevealed && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="px-3 pb-3 pt-1 border-t bg-muted/30 space-y-2">
                            {control.comment && (
                              <p className="text-xs text-muted-foreground">{control.comment}</p>
                            )}
                            {control.aiExplanation ? (
                              <div className="flex gap-2 items-start">
                                <Sparkles className="h-3.5 w-3.5 text-accent mt-0.5 flex-shrink-0" />
                                <p className="text-xs leading-relaxed text-foreground/80">{control.aiExplanation}</p>
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground italic">No AI explanation available for this control.</p>
                            )}
                            {control.evidenceSource && control.evidenceSource !== "No evidence found" && control.evidenceSource !== "No documents uploaded" && (
                              (() => {
                                const isUrl = control.evidenceSource!.startsWith("http");
                                return (
                                  <div className="flex items-center gap-2 mt-1">
                                    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                                      isUrl
                                        ? "bg-primary/10 text-primary border border-primary/20"
                                        : "bg-accent/10 text-accent border border-accent/20"
                                    }`}>
                                      {isUrl ? <Globe className="h-2.5 w-2.5" /> : <FileText className="h-2.5 w-2.5" />}
                                      {isUrl ? "Public Source" : "Uploaded Document"}
                                    </span>
                                    {isUrl ? (
                                      <a
                                        href={control.evidenceSource}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-1 group/evidence cursor-pointer hover:opacity-80 transition-opacity"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <span className="text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors truncate max-w-[250px] underline underline-offset-2">
                                          {control.evidenceSource}
                                        </span>
                                        <ExternalLink className="h-2.5 w-2.5 text-muted-foreground flex-shrink-0" />
                                      </a>
                                    ) : (
                                      <button
                                        className="flex items-center gap-1 group/evidence cursor-pointer hover:opacity-80 transition-opacity"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          onNavigateToDocs?.(control.evidenceSource);
                                        }}
                                      >
                                        <span className="text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2">
                                          {control.evidenceSource}
                                        </span>
                                        <ExternalLink className="h-2.5 w-2.5 text-muted-foreground flex-shrink-0" />
                                      </button>
                                    )}
                                  </div>
                                );
                              })()
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
