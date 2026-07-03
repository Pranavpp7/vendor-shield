import { useEffect, useRef, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  BookOpenCheck,
  FileUp,
  Loader2,
  Save,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  deleteFramework,
  extractFrameworkFromFile,
  fetchFrameworks,
  saveFramework,
} from "@/lib/api";
import { FrameworkDraft, FrameworkSummary } from "@/types/assessment";

export default function Frameworks() {
  const [frameworks, setFrameworks] = useState<FrameworkSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<FrameworkDraft | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = () => {
    setLoadingList(true);
    fetchFrameworks()
      .then(setFrameworks)
      .catch((err) => toast.error(`Failed to load frameworks: ${err.message}`))
      .finally(() => setLoadingList(false));
  };

  useEffect(refresh, []);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setExtracting(true);
    try {
      const d = await extractFrameworkFromFile(file);
      setDraft(d);
      toast.success(
        `Drafted ${d.controls.length} control(s) from ${file.name}. Review and edit before saving.`
      );
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setExtracting(false);
    }
  };

  const updateDraft = (patch: Partial<FrameworkDraft>) =>
    setDraft((prev) => (prev ? { ...prev, ...patch } : prev));

  const updateControl = (index: number, field: string, value: string) =>
    setDraft((prev) => {
      if (!prev) return prev;
      const controls = [...prev.controls];
      controls[index] = { ...controls[index], [field]: value };
      return { ...prev, controls };
    });

  const removeControl = (index: number) =>
    setDraft((prev) =>
      prev ? { ...prev, controls: prev.controls.filter((_, i) => i !== index) } : prev
    );

  const handleSave = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const saved = await saveFramework(draft);
      toast.success(`Framework "${saved.name}" saved with ${saved.control_count} controls.`);
      setDraft(null);
      refresh();
    } catch (err: any) {
      toast.error(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (fw: FrameworkSummary) => {
    if (!window.confirm(`Delete custom framework "${fw.name}"? Past assessments keep their results.`)) return;
    try {
      await deleteFramework(fw.id);
      toast.success(`Deleted ${fw.name}.`);
      refresh();
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">Frameworks</h1>
          <p className="text-muted-foreground">
            Assessments score vendors against a control framework. Use the
            built-in ones, or upload your own standard — a questionnaire,
            policy checklist, or excerpt of ISO 27001 — and VendorShield will
            draft it as a framework for you to review.
          </p>
        </div>

        {/* Existing frameworks */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpenCheck className="h-4 w-4" />
              Available frameworks
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {loadingList ? (
              <div className="flex justify-center py-6">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              frameworks.map((fw) => (
                <div key={fw.id} className="flex items-start justify-between gap-3 rounded-lg border p-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{fw.name}</span>
                      <Badge variant={fw.custom ? "default" : "outline"}>
                        {fw.custom ? "Custom" : "Built-in"}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {fw.control_count} controls · {fw.domains.length} domains
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{fw.description}</p>
                  </div>
                  {fw.custom && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0 text-muted-foreground hover:text-red-500"
                      onClick={() => handleDelete(fw)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Extract from document */}
        {!draft && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileUp className="h-4 w-4" />
                Create a framework from a document
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-accent transition-colors"
                onClick={() => !extracting && fileInputRef.current?.click()}
              >
                {extracting ? (
                  <>
                    <Loader2 className="h-8 w-8 mx-auto mb-2 animate-spin text-accent" />
                    <p className="text-sm text-muted-foreground">
                      Reading the document and drafting controls… this takes up to a minute.
                    </p>
                  </>
                ) : (
                  <>
                    <FileUp className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Click to upload a PDF, DOCX, or text file containing your standard
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      The AI drafts the controls — nothing is saved until you review it
                    </p>
                  </>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx,.txt,.md"
                  onChange={handleFile}
                />
              </div>
            </CardContent>
          </Card>
        )}

        {/* Draft review & edit */}
        {draft && (
          <Card className="border-accent/40">
            <CardHeader>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <CardTitle className="text-base">
                  Review draft{draft.source_document ? ` — from ${draft.source_document}` : ""}
                </CardTitle>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setDraft(null)}>
                    <X className="h-3.5 w-3.5 mr-1.5" />
                    Discard
                  </Button>
                  <Button size="sm" onClick={handleSave} disabled={saving || draft.controls.length === 0}>
                    {saving ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    ) : (
                      <Save className="h-3.5 w-3.5 mr-1.5" />
                    )}
                    Save framework
                  </Button>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                These fields drive retrieval and scoring — check that each
                control's search query and standard actually match your document
                before saving.
              </p>
              {draft.source_truncated && (
                <p className="text-xs text-amber-600 flex items-center gap-1">
                  <TriangleAlert className="h-3.5 w-3.5" />
                  The document was long, so only the beginning was used for extraction.
                </p>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Framework name</Label>
                  <Input
                    value={draft.name}
                    onChange={(e) => updateDraft({ name: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">ID (URL-safe slug)</Label>
                  <Input
                    value={draft.id}
                    onChange={(e) => updateDraft({ id: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Description</Label>
                <Textarea
                  className="min-h-[60px]"
                  value={draft.description}
                  onChange={(e) => updateDraft({ description: e.target.value })}
                />
              </div>

              <p className="text-sm font-medium">{draft.controls.length} draft control(s)</p>
              <Accordion type="multiple" className="space-y-2">
                {draft.controls.map((c, i) => (
                  <AccordionItem key={`${c.id}-${i}`} value={`${c.id}-${i}`} className="border rounded-lg px-3">
                    <AccordionTrigger className="hover:no-underline py-3">
                      <div className="flex items-center gap-2 text-sm text-left">
                        <Badge variant="outline">{c.id}</Badge>
                        <span className="font-medium">{c.title}</span>
                        <span className="text-xs text-muted-foreground">{c.domain}</span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="space-y-3 pb-4">
                      <div className="grid sm:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Title</Label>
                          <Input value={c.title} onChange={(e) => updateControl(i, "title", e.target.value)} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Domain</Label>
                          <Input value={c.domain} onChange={(e) => updateControl(i, "domain", e.target.value)} />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Description</Label>
                        <Textarea className="min-h-[60px]" value={c.description}
                          onChange={(e) => updateControl(i, "description", e.target.value)} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Search query (drives evidence retrieval)</Label>
                        <Textarea className="min-h-[50px]" value={c.search_query}
                          onChange={(e) => updateControl(i, "search_query", e.target.value)} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">What to look for</Label>
                        <Textarea className="min-h-[60px]" value={c.what_to_look_for}
                          onChange={(e) => updateControl(i, "what_to_look_for", e.target.value)} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">What good looks like (the standard)</Label>
                        <Textarea className="min-h-[60px]" value={c.what_good_looks_like}
                          onChange={(e) => updateControl(i, "what_good_looks_like", e.target.value)} />
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-red-500 hover:text-red-600"
                        onClick={() => removeControl(i)}
                      >
                        <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                        Remove this control
                      </Button>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
