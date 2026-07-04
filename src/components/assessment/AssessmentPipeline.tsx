import { Check, Loader2, AlertTriangle, XCircle, FileSearch, Database, Brain, Calculator, Save } from "lucide-react";

export type PipelineEvent = {
  step: string;    // backend step key (services/progress.py contract)
  message: string;
  percent: number;
};

type StageState = "pending" | "active" | "done" | "warn" | "error" | "skipped";

const STAGES = [
  { key: "ingest", label: "Ingest", icon: Database },
  { key: "retrieve", label: "Retrieve", icon: FileSearch },
  { key: "evaluate", label: "Score", icon: Brain },
  { key: "aggregate", label: "Aggregate", icon: Calculator },
  { key: "save", label: "Save", icon: Save },
] as const;

// Map every backend step key onto a pipeline stage index
const STEP_TO_STAGE: Record<string, number> = {
  ingest: 0,
  retrieve: 1,
  sparse_evidence: 1,
  no_documents: 1,
  evaluate: 2,
  re_retrieve: 2,
  aggregate: 3,
  save: 4,
  complete: 5, // past the last stage → everything done
};

// Steps that put an amber "warn" treatment on their stage
const WARN_STEPS = new Set(["sparse_evidence", "re_retrieve", "no_documents"]);

/**
 * Live view of the LangGraph assessment workflow: one node per graph
 * stage, driven by the SSE progress events the backend emits from each
 * node. State is never conveyed by color alone — each stage carries an
 * icon (check / spinner / warning triangle) and a label.
 */
export function AssessmentPipeline({ event }: { event: PipelineEvent | null }) {
  const step = event?.step ?? "idle";
  const isError = step === "error";
  const currentStage = isError ? -1 : STEP_TO_STAGE[step] ?? (step === "idle" ? -1 : 0);

  const stateFor = (index: number): StageState => {
    if (isError) return index < 0 ? "error" : "pending";
    if (currentStage > index) {
      // no_documents skips scoring + aggregation entirely
      if (step === "no_documents" && (index === 2 || index === 3)) return "skipped";
      return "done";
    }
    if (currentStage === index) {
      if (WARN_STEPS.has(step)) return "warn";
      return "active";
    }
    return "pending";
  };

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3" aria-live="polite">
      <div className="flex items-start">
        {STAGES.map((stage, i) => {
          const state = stateFor(i);
          const Icon = stage.icon;
          return (
            <div key={stage.key} className="flex-1 flex flex-col items-center relative">
              {/* Connector line to the previous node */}
              {i > 0 && (
                <div
                  className={`absolute right-1/2 left-[-50%] top-[15px] h-0.5 ${
                    stateFor(i - 1) === "done" || stateFor(i - 1) === "skipped"
                      ? "bg-accent"
                      : "bg-border"
                  }`}
                />
              )}
              <div
                className={`relative z-10 h-8 w-8 rounded-full border-2 flex items-center justify-center bg-card transition-colors duration-300 ${
                  state === "done"
                    ? "border-accent bg-accent text-accent-foreground"
                    : state === "active"
                    ? "border-accent text-accent"
                    : state === "warn"
                    ? "border-amber-500 text-amber-600"
                    : state === "skipped"
                    ? "border-border text-muted-foreground/50"
                    : "border-border text-muted-foreground/60"
                }`}
              >
                {state === "done" ? (
                  <Check className="h-4 w-4" />
                ) : state === "active" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : state === "warn" ? (
                  <AlertTriangle className="h-4 w-4" />
                ) : (
                  <Icon className="h-3.5 w-3.5" />
                )}
                {state === "active" && (
                  <span className="absolute inset-0 rounded-full border-2 border-accent animate-ping opacity-30" />
                )}
              </div>
              <span
                className={`mt-1.5 text-[11px] font-medium ${
                  state === "pending" || state === "skipped"
                    ? "text-muted-foreground/60"
                    : state === "warn"
                    ? "text-amber-600"
                    : "text-foreground"
                }`}
              >
                {stage.label}
                {state === "skipped" && " (skipped)"}
              </span>
            </div>
          );
        })}
      </div>

      {/* Message + progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 text-xs min-h-[16px]">
          {isError ? (
            <>
              <XCircle className="h-3.5 w-3.5 text-risk-high shrink-0" />
              <span className="text-risk-high">{event?.message || "Assessment failed"}</span>
            </>
          ) : (
            <span className="text-muted-foreground">
              {event?.message || "Waiting for the agent to start…"}
            </span>
          )}
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isError ? "bg-risk-high" : "bg-accent"
            }`}
            style={{ width: `${event?.percent ?? 0}%` }}
          />
        </div>
      </div>
    </div>
  );
}
