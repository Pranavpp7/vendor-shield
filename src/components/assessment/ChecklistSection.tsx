import { ControlResult } from "@/types/assessment";
import { Check, X, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

type Props = {
  controls: ControlResult[];
  isRunning?: boolean;
  revealedCount?: number;
};

export function ChecklistSection({ controls, isRunning, revealedCount = controls.length }: Props) {
  const categories = [...new Set(controls.map((c) => c.category))];

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

                return (
                  <motion.div
                    key={control.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: globalIdx * 0.08, duration: 0.3 }}
                    className="flex items-center gap-3 p-3 rounded-lg bg-card border"
                  >
                    {!isRevealed ? (
                      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    ) : control.passed ? (
                      <div className="h-5 w-5 rounded-full bg-risk-low-bg flex items-center justify-center flex-shrink-0">
                        <Check className="h-3 w-3 text-risk-low" />
                      </div>
                    ) : (
                      <div className="h-5 w-5 rounded-full bg-risk-high-bg flex items-center justify-center flex-shrink-0">
                        <X className="h-3 w-3 text-risk-high" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{control.name}</p>
                      {isRevealed && control.comment && (
                        <p className="text-xs text-muted-foreground mt-0.5">{control.comment}</p>
                      )}
                    </div>
                    {!isRevealed && (
                      <span className="text-xs text-muted-foreground italic">Analyzing…</span>
                    )}
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
