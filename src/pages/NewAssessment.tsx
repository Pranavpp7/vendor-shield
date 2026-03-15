import { useState, useCallback, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { vendorNameToSlug } from "@/lib/utils";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAssessments } from "@/context/AssessmentContext";
import { useChecklistSchema } from "@/hooks/useChecklistSchema";
import { generateChecklistFromAI } from "@/lib/api";
import { saveRunSnapshot } from "@/lib/runHistory";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Upload, Link as LinkIcon, X, ArrowRight, ArrowLeft, Loader2, Save } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/context/AuthContext";

export default function NewAssessment() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { addAssessment, getAssessment, updateAssessment } = useAssessments();
  const { toast } = useToast();
  const { user } = useAuth();
  const { allControls: checklistAllControls } = useChecklistSchema();
  const [draftId, setDraftId] = useState<string | null>(null);
  const [step, setStep] = useState(1);
  const [vendorName, setVendorName] = useState("");
  const [files, setFiles] = useState<{ name: string; size: number }[]>([]);
  const [rawFiles, setRawFiles] = useState<File[]>([]);
  const [links, setLinks] = useState<string[]>([]);
  const [linkInput, setLinkInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Load draft if editing
  useEffect(() => {
    const id = searchParams.get("draft");
    if (id) {
      const draft = getAssessment(id);
      if (draft && draft.status === "Draft") {
        setDraftId(id);
        setVendorName(draft.vendorName);
        setFiles(draft.uploadedFiles);
        setLinks(draft.links);
      }
    }
  }, [searchParams, getAssessment]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    setRawFiles((prev) => [...prev, ...dropped]);
    setFiles((prev) => [...prev, ...dropped.map((f) => ({ name: f.name, size: f.size }))]);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files);
    setRawFiles((prev) => [...prev, ...selected]);
    setFiles((prev) => [...prev, ...selected.map((f) => ({ name: f.name, size: f.size }))]);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, j) => j !== index));
    setRawFiles((prev) => prev.filter((_, j) => j !== index));
  };

  const addLink = () => {
    if (linkInput.trim()) {
      setLinks((prev) => [...prev, linkInput.trim()]);
      setLinkInput("");
    }
  };

  const uploadFilesToStorage = async (assessmentId: string) => {
    if (rawFiles.length === 0) return;
    setUploading(true);
    for (const file of rawFiles) {
      try {
        const storagePath = `${assessmentId}/${Date.now()}-${file.name}`;
        const { error: uploadErr } = await supabase.storage
          .from("vendor-documents")
          .upload(storagePath, file);
        if (uploadErr) throw uploadErr;

        const { data: docRecord, error: docErr } = await supabase
          .from("documents")
          .insert({
            assessment_id: assessmentId,
            file_name: file.name,
            file_size: file.size,
            content_type: file.type || "application/octet-stream",
            storage_path: storagePath,
            status: "pending",
            user_id: user?.id,
          })
          .select("id")
          .single();
        if (docErr) throw docErr;

        supabase.functions.invoke("parse-document", {
          body: { documentId: docRecord.id },
        }).catch((err) => console.error("Parse error:", err));
      } catch (err: any) {
        console.error("Upload error:", err);
        toast({ title: "Upload failed", description: `Failed to upload ${file.name}: ${err.message}`, variant: "destructive" });
      }
    }
    setUploading(false);
  };

  const saveDraft = async () => {
    if (!vendorName.trim()) return;
    const id = draftId || `${vendorNameToSlug(vendorName)}-${crypto.randomUUID().slice(0, 8)}`;
    const data = {
      id,
      vendorName,
      criticality: "Medium" as const,
      createdAt: new Date().toISOString().split("T")[0],
      status: "Draft" as const,
      score: 0,
      riskLevel: "Low" as const,
      controls: [],
      notes: "",
      chatHistory: [],
      uploadedFiles: files,
      links,
    };
    if (draftId) await updateAssessment(draftId, data);
    else await addAssessment(data);
    await uploadFilesToStorage(id);
    toast({ title: "Draft saved", description: `Assessment for ${vendorName} saved as draft.` });
    navigate("/assessments");
  };

  const [statusMessage, setStatusMessage] = useState("");

  const waitForDocumentsReady = async (assessmentId: string, maxWaitMs = 120000) => {
    const pollInterval = 3000;
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      const { data: docs } = await supabase
        .from("documents")
        .select("id, status")
        .eq("assessment_id", assessmentId);
      if (!docs || docs.length === 0) return true;
      const pending = docs.filter((d) => d.status !== "ready" && d.status !== "error");
      if (pending.length === 0) return true;
      setStatusMessage(`Indexing documents… (${docs.length - pending.length}/${docs.length} ready)`);
      await new Promise((r) => setTimeout(r, pollInterval));
    }
    return false;
  };

  const startAssessment = async () => {
    setLoading(true);
    const id = draftId || `${vendorNameToSlug(vendorName)}-${crypto.randomUUID().slice(0, 8)}`;

    // Upload files to storage first
    setStatusMessage("Uploading files…");
    await uploadFilesToStorage(id);

    // Submit links to parse-url
    if (links.length > 0) {
      setStatusMessage("Submitting links for indexing…");
      await Promise.all(
        links.map((url) =>
          supabase.functions.invoke("parse-url", {
            body: { url, assessmentId: id, userId: user?.id },
          }).catch((err) => console.error("parse-url error:", err))
        )
      );
    }

    // Wait for all documents (files + URLs) to be indexed before running AI checklist
    if (rawFiles.length > 0 || links.length > 0) {
      setStatusMessage("Waiting for documents to be indexed…");
      const allReady = await waitForDocumentsReady(id);
      if (!allReady) {
        toast({ title: "Some documents still indexing", description: "The checklist will run with available data. You can re-run it later from the assessment page." });
      }
    }

    setStatusMessage("Running AI checklist…");
    const result = await generateChecklistFromAI(vendorName, checklistAllControls, id);

    const assessmentData = {
      id,
      vendorName,
      criticality: "Medium" as const,
      createdAt: new Date().toISOString().split("T")[0],
      status: "Completed" as const,
      score: result.score,
      riskLevel: result.riskLevel as "Low" | "Medium" | "High",
      controls: result.controls,
      notes: "",
      chatHistory: [],
      uploadedFiles: files,
      links,
    };

    if (draftId) await updateAssessment(draftId, assessmentData);
    else await addAssessment(assessmentData);

    // Save run snapshot for history tracking
    if (user) {
      await saveRunSnapshot(id, user.id, result.score, result.riskLevel, result.controls);
    }

    navigate(`/assessments/${id}`);
  };

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold tracking-tight mb-2">New Assessment</h1>
        <p className="text-muted-foreground mb-8">Step {step} of 2</p>

        {step === 1 ? (
          <Card>
            <CardHeader>
              <CardTitle>Vendor Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="vendor">Vendor Name</Label>
                <Input
                  id="vendor"
                  placeholder="e.g., ServiceNow, SAP"
                  value={vendorName}
                  onChange={(e) => setVendorName(e.target.value)}
                />
              </div>
              <Button
                onClick={() => setStep(2)}
                disabled={!vendorName.trim()}
                className="w-full"
              >
                Next: Upload Docs <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Documents & Links</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-accent transition-colors"
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => document.getElementById("file-upload")?.click()}
              >
                <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Drag & drop files here, or click to browse
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  PDF, DOCX, XLSX — UI only, no parsing
                </p>
                <input
                  id="file-upload"
                  type="file"
                  className="hidden"
                  multiple
                  onChange={handleFileInput}
                />
              </div>

              {files.length > 0 && (
                <div className="space-y-2">
                  {files.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between p-2 rounded bg-muted text-sm"
                    >
                      <span>
                        {f.name} ({(f.size / 1024).toFixed(1)} KB)
                      </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={() => removeFile(i)}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                    </div>
                  ))}
                </div>
              )}

              <div className="space-y-2">
                <Label>Add Links</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="https://..."
                    value={linkInput}
                    onChange={(e) => setLinkInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addLink()}
                  />
                  <Button variant="outline" onClick={addLink}>
                    <LinkIcon className="h-4 w-4" />
                  </Button>
                </div>
                {links.map((l, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-muted text-sm"
                  >
                    <span className="truncate">{l}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => setLinks((prev) => prev.filter((_, j) => j !== i))}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep(1)}>
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back
                </Button>
                <Button variant="secondary" onClick={saveDraft} disabled={loading || !vendorName.trim()}>
                  <Save className="h-4 w-4 mr-2" />
                  Save Draft
                </Button>
                <Button onClick={startAssessment} disabled={loading || uploading} className="flex-1">
                  {loading || uploading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {statusMessage || (uploading ? "Uploading Files…" : "Running Assessment…")}
                    </>
                  ) : (
                    "Start Assessment"
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
