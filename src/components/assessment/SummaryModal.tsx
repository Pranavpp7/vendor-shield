import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, FileText } from "lucide-react";
import { generateSummaryFromAI } from "@/lib/api";
import { Assessment } from "@/types/assessment";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessment: Assessment;
};

export function SummaryModal({ open, onOpenChange, assessment }: Props) {
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    const result = await generateSummaryFromAI(
      assessment.vendorName,
      assessment.score,
      assessment.riskLevel,
      assessment.controls,
      assessment.notes
    );
    setSummary(result);
    setLoading(false);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setSummary(null); }}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Assessment Summary — {assessment.vendorName}
          </DialogTitle>
        </DialogHeader>
        {!summary ? (
          <div className="flex flex-col items-center py-8 gap-4">
            <p className="text-sm text-muted-foreground">Generate a risk posture summary using AI.</p>
            <Button onClick={generate} disabled={loading}>
              {loading ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating…</>
              ) : (
                "Generate Summary"
              )}
            </Button>
          </div>
        ) : (
          <div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed">{summary}</div>
            <div className="mt-4 pt-4 border-t">
              <Button variant="outline" size="sm" disabled>
                <FileText className="h-4 w-4 mr-2" />
                Download PDF (coming soon)
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
