import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BookOpenCheck, ArrowRight, Loader2, Settings as SettingsIcon } from "lucide-react";
import { fetchFrameworks } from "@/lib/api";
import { FrameworkSummary } from "@/types/assessment";

/**
 * Settings.  The old page hosted a local-only checklist editor that
 * silently did nothing to real assessments (controls live in backend
 * framework JSON, not the frontend).  It now tells the truth: control
 * frameworks are managed on the Frameworks page, where edits actually
 * apply — including creating your own framework from an uploaded
 * standard.
 */
export default function Settings() {
  const navigate = useNavigate();
  const [frameworks, setFrameworks] = useState<FrameworkSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFrameworks()
      .then(setFrameworks)
      .catch((err) => console.error("Failed to load frameworks:", err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <SettingsIcon className="h-5 w-5" />
            Settings
          </h1>
          <p className="text-sm text-muted-foreground">
            Assessment configuration
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <BookOpenCheck className="h-4 w-4" />
              Control Frameworks
            </CardTitle>
            <CardDescription>
              Assessments score vendors against a control framework. Frameworks
              are data, not settings — view them, or create your own by
              uploading a security standard, on the Frameworks page.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <div className="flex justify-center py-6">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              frameworks.map((fw) => (
                <div key={fw.id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{fw.name}</span>
                      <Badge variant={fw.custom ? "default" : "outline"}>
                        {fw.custom ? "Custom" : "Built-in"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {fw.control_count} controls · {fw.domains.join(" · ")}
                    </p>
                  </div>
                </div>
              ))
            )}
            <Button variant="outline" onClick={() => navigate("/frameworks")}>
              Manage frameworks
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Model & Scoring</CardTitle>
            <CardDescription>
              LLM model, concurrency, confidence thresholds, and evidence
              staleness are configured server-side in{" "}
              <code className="text-xs bg-muted px-1 py-0.5 rounded">backend/.env</code>{" "}
              — see the backend README for every variable. Model changes must
              pass the eval gate (<code className="text-xs bg-muted px-1 py-0.5 rounded">uv run python evals/run_evals.py</code>).
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </AppLayout>
  );
}
