import { useState } from "react";
import { ControlResult, UploadedFile } from "@/types/assessment";
import { Check, X, AlertCircle, Loader2, ChevronDown, ChevronUp, Sparkles, FileText, ExternalLink, Download, FolderOpen, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";

type Props = {
  controls: ControlResult[];
  isRunning?: boolean;
  revealedCount?: number;
  uploadedFiles?: UploadedFile[];
  links?: string[];
  onNavigateToDocs?: () => void;
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

export function ChecklistSection({ controls, isRunning, revealedCount = controls.length, uploadedFiles = [], links = [], onNavigateToDocs }: Props) {
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
                            {control.evidenceSource && (() => {
                              const matchedFile = uploadedFiles.find(f => 
                                f.name.toLowerCase().includes(control.evidenceSource!.toLowerCase().split(' ')[0].toLowerCase()) ||
                                control.evidenceSource!.toLowerCase().includes(f.name.split('.')[0].toLowerCase())
                              );
                              const matchedLink = links.find(l => 
                                l.toLowerCase().includes(control.evidenceSource!.toLowerCase().split(' ')[0].toLowerCase())
                              );
                              return (
                                <Popover>
                                  <PopoverTrigger asChild>
                                    <button className="flex items-center gap-1.5 mt-1 group/evidence cursor-pointer hover:opacity-80 transition-opacity">
                                      <FileText className="h-3 w-3 text-muted-foreground" />
                                      <span className="text-[10px] font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded border border-accent/20 group-hover/evidence:border-accent/40 transition-colors">
                                        {control.evidenceSource}
                                      </span>
                                    </button>
                                  </PopoverTrigger>
                                  <PopoverContent className="w-72 p-0" align="start">
                                    <div className="p-3 border-b">
                                      <p className="text-xs font-semibold flex items-center gap-1.5">
                                        <FileText className="h-3.5 w-3.5 text-accent" />
                                        Evidence Source
                                      </p>
                                      <p className="text-[11px] text-muted-foreground mt-1">{control.evidenceSource}</p>
                                    </div>
                                    <div className="p-3 space-y-2">
                                      {matchedFile ? (
                                        <div className="flex items-center justify-between p-2 rounded-md bg-muted/50">
                                          <div className="flex items-center gap-2 min-w-0">
                                            <FileText className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                                            <div className="min-w-0">
                                              <p className="text-xs font-medium truncate">{matchedFile.name}</p>
                                              <p className="text-[10px] text-muted-foreground">{(matchedFile.size / 1024).toFixed(1)} KB</p>
                                            </div>
                                          </div>
                                          <Button variant="ghost" size="icon" className="h-6 w-6 flex-shrink-0">
                                            <Download className="h-3 w-3" />
                                          </Button>
                                        </div>
                                      ) : matchedLink ? (
                                        <a href={matchedLink} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 p-2 rounded-md bg-muted/50 hover:bg-muted transition-colors text-xs text-accent hover:underline">
                                          <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
                                          <span className="truncate">{matchedLink}</span>
                                        </a>
                                      ) : (
                                        <div className="text-center py-2">
                                          <p className="text-[11px] text-muted-foreground">Document not yet uploaded</p>
                                          {onNavigateToDocs && (
                                            <Button variant="outline" size="sm" className="mt-2 h-7 text-xs" onClick={onNavigateToDocs}>
                                              <FolderOpen className="h-3 w-3 mr-1" />
                                              Go to Documents
                                            </Button>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  </PopoverContent>
                                </Popover>
                              );
                            })()}
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
