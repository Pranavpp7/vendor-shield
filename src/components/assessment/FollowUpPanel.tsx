import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, Loader2, MessageSquareText, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { fetchFollowUpQuestions, generateFollowUpQuestions } from "@/lib/api";
import { FollowUpQuestion } from "@/types/assessment";

type Props = {
  assessmentId: string;
  vendorName: string;
};

/**
 * Turns assessment gaps into a vendor-facing question list: one specific,
 * answerable question per control that didn't fully pass. Generated once
 * and persisted; regenerate after re-runs or overrides.
 */
export function FollowUpPanel({ assessmentId, vendorName }: Props) {
  const [questions, setQuestions] = useState<FollowUpQuestion[] | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchFollowUpQuestions(assessmentId)
      .then((data) => {
        if (data) {
          setQuestions(data.questions);
          setGeneratedAt(data.generated_at);
        }
      })
      .catch((err) => console.error("Failed to load follow-up questions:", err))
      .finally(() => setLoading(false));
  }, [assessmentId]);

  const generate = async () => {
    setGenerating(true);
    try {
      const data = await generateFollowUpQuestions(assessmentId);
      setQuestions(data.questions);
      setGeneratedAt(data.generated_at);
      toast.success(
        data.questions.length === 0
          ? "All controls passed — nothing to ask the vendor."
          : `Generated ${data.questions.length} follow-up question(s).`
      );
    } catch (err: any) {
      toast.error(`Generation failed: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const copyAll = () => {
    if (!questions?.length) return;
    const text = [
      `Follow-up questions for ${vendorName}:`,
      "",
      ...questions.map((q, i) => `${i + 1}. [${q.control_id}] ${q.question}`),
    ].join("\n");
    navigator.clipboard.writeText(text);
    toast.success("Copied all questions to clipboard.");
  };

  const byDomain = (questions ?? []).reduce<Record<string, FollowUpQuestion[]>>(
    (acc, q) => {
      (acc[q.domain || "Other"] ??= []).push(q);
      return acc;
    },
    {}
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquareText className="h-4 w-4" />
            Vendor Follow-up Questions
            {generatedAt && (
              <span className="text-xs font-normal text-muted-foreground">
                generated {new Date(generatedAt).toLocaleString()}
              </span>
            )}
          </CardTitle>
          <div className="flex gap-2">
            {questions && questions.length > 0 && (
              <Button variant="outline" size="sm" onClick={copyAll}>
                <Copy className="h-3.5 w-3.5 mr-1.5" />
                Copy all
              </Button>
            )}
            <Button size="sm" onClick={generate} disabled={generating}>
              {generating ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              )}
              {questions ? "Regenerate" : "Generate questions"}
            </Button>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          One specific, answerable question per gapped control — ready to paste
          into an email to the vendor.
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : !questions ? (
          <p className="text-sm text-muted-foreground">
            No questions generated yet. Click "Generate questions" to draft one
            for every control that didn't fully pass.
          </p>
        ) : questions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            All controls passed — there is nothing to ask this vendor. 🎉
          </p>
        ) : (
          <div className="space-y-5">
            {Object.entries(byDomain).map(([domain, qs]) => (
              <div key={domain} className="space-y-2">
                <p className="text-sm font-semibold">{domain}</p>
                {qs.map((q) => (
                  <div key={q.control_id} className="rounded-lg border p-3 space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{q.control_id}</Badge>
                    </div>
                    <p className="text-sm">{q.question}</p>
                    {q.rationale && (
                      <p className="text-xs text-muted-foreground">{q.rationale}</p>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
