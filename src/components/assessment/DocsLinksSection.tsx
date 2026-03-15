import { useState, useEffect, useRef } from "react";
import { UploadedFile } from "@/types/assessment";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FileText, Link as LinkIcon, Plus, X, Pencil, Check, Upload, Loader2, CheckCircle, AlertCircle, RefreshCw, Trash2, Eye, Download } from "lucide-react";
import { IndexingPipelineFlow } from "./IndexingPipelineFlow";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

type DocumentRecord = {
  id: string;
  file_name: string;
  file_size: number;
  status: string;
  storage_path: string | null;
  created_at: string;
};

type Props = {
  files: UploadedFile[];
  links: string[];
  onUpdateFiles: (files: UploadedFile[]) => void;
  onUpdateLinks: (links: string[]) => void;
  assessmentId?: string;
  onRerunChecklist?: () => void;
  highlightDoc?: string | null;
  onClearHighlight?: () => void;
};

export function DocsLinksSection({ files, links, onUpdateFiles, onUpdateLinks, assessmentId, onRerunChecklist }: Props) {
  const { user } = useAuth();
  const [linkInput, setLinkInput] = useState("");
  const [editingLink, setEditingLink] = useState<number | null>(null);
  const [editLinkValue, setEditLinkValue] = useState("");
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ docId: string; fileIndex: number; fileName: string } | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewName, setPreviewName] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!assessmentId) return;
    loadDocuments();
  }, [assessmentId]);

  const loadDocuments = async () => {
    if (!assessmentId) return;
    const { data } = await supabase
      .from("documents")
      .select("id, file_name, file_size, status, storage_path, created_at")
      .eq("assessment_id", assessmentId)
      .order("created_at", { ascending: false });
    if (data) setDocuments(data as DocumentRecord[]);
  };

  useEffect(() => {
    const processing = documents.some(d => d.status === "pending" || d.status === "processing");
    if (!processing) return;
    const interval = setInterval(loadDocuments, 3000);
    return () => clearInterval(interval);
  }, [documents]);

  const addLink = () => {
    if (linkInput.trim()) {
      onUpdateLinks([...links, linkInput.trim()]);
      setLinkInput("");
    }
  };

  const removeLink = (i: number) => onUpdateLinks(links.filter((_, j) => j !== i));

  const startEditLink = (i: number) => {
    setEditingLink(i);
    setEditLinkValue(links[i]);
  };

  const saveEditLink = () => {
    if (editingLink !== null && editLinkValue.trim()) {
      const updated = [...links];
      updated[editingLink] = editLinkValue.trim();
      onUpdateLinks(updated);
      setEditingLink(null);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !assessmentId) {
      if (e.target.files) {
        const selected = Array.from(e.target.files).map((f) => ({ name: f.name, size: f.size }));
        onUpdateFiles([...files, ...selected]);
      }
      return;
    }

    setUploading(true);
    const selectedFiles = Array.from(e.target.files);

    for (const file of selectedFiles) {
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
        }).then(() => {
          loadDocuments();
        }).catch((err) => {
          console.error("Parse error:", err);
          loadDocuments();
        });

        onUpdateFiles([...files, { name: file.name, size: file.size }]);
        toast.success(`Uploaded ${file.name}`);
      } catch (err: any) {
        console.error("Upload error:", err);
        toast.error(`Failed to upload ${file.name}: ${err.message}`);
      }
    }

    setUploading(false);
    loadDocuments();
    e.target.value = "";
  };

  const reprocessDocument = async (docId: string, fileName: string) => {
    setReprocessingId(docId);
    try {
      await supabase.from("documents").update({ status: "pending" }).eq("id", docId);
      loadDocuments();

      const { error } = await supabase.functions.invoke("parse-document", {
        body: { documentId: docId },
      });

      if (error) throw error;
      toast.success(`Re-processing ${fileName}`);
    } catch (err: any) {
      console.error("Reprocess error:", err);
      toast.error(`Failed to re-process ${fileName}: ${err.message}`);
    } finally {
      setReprocessingId(null);
      loadDocuments();
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      // Get storage path before deleting the record
      const { data: docData } = await supabase
        .from("documents")
        .select("storage_path")
        .eq("id", deleteTarget.docId)
        .single();

      // Delete from DB (chunks cascade via FK)
      await supabase.from("document_chunks").delete().eq("document_id", deleteTarget.docId);
      await supabase.from("documents").delete().eq("id", deleteTarget.docId);

      // Delete from storage bucket
      if (docData?.storage_path) {
        await supabase.storage.from("vendor-documents").remove([docData.storage_path]);
      }
      
      // Remove from local files
      onUpdateFiles(files.filter((_, j) => j !== deleteTarget.fileIndex));
      toast.success(`Deleted ${deleteTarget.fileName}`);
      loadDocuments();
    } catch (err: any) {
      toast.error(`Failed to delete: ${err.message}`);
    } finally {
      setDeleteTarget(null);
    }
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case "ready":
        return <Badge variant="outline" className="text-[10px] gap-1 text-risk-low border-risk-low/30"><CheckCircle className="h-2.5 w-2.5" />Indexed</Badge>;
      case "processing":
        return <Badge variant="outline" className="text-[10px] gap-1 text-amber-500 border-amber-500/30"><Loader2 className="h-2.5 w-2.5 animate-spin" />Processing</Badge>;
      case "pending":
        return <Badge variant="outline" className="text-[10px] gap-1 text-muted-foreground"><Loader2 className="h-2.5 w-2.5 animate-spin" />Pending</Badge>;
      case "error":
        return <Badge variant="outline" className="text-[10px] gap-1 text-risk-high border-risk-high/30"><AlertCircle className="h-2.5 w-2.5" />Error</Badge>;
      default:
        return null;
    }
  };

  const hasReadyDocs = documents.some(d => d.status === "ready");

  return (
    <div className="space-y-4">
      {/* Re-run checklist banner */}
      {hasReadyDocs && onRerunChecklist && (
        <Card className="border-accent/30 bg-accent/5">
          <CardContent className="pt-4 pb-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Documents have been indexed</p>
              <p className="text-xs text-muted-foreground">Re-run the checklist to incorporate new document findings into the assessment.</p>
            </div>
            <Button size="sm" onClick={onRerunChecklist}>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              Re-run Checklist
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-4 w-4" /> Documents ({files.length})
              </CardTitle>
              {assessmentId && documents.length > 0 && (
                <IndexingPipelineFlow assessmentId={assessmentId} documents={documents.map(d => ({ id: d.id, file_name: d.file_name, status: d.status }))} />
              )}
              <Button
                variant="outline"
                size="sm"
                disabled={uploading}
                onClick={() => document.getElementById("detail-file-upload")?.click()}
              >
                {uploading ? (
                  <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Uploading…</>
                ) : (
                  <><Upload className="h-3 w-3 mr-1" /> Upload</>
                )}
              </Button>
              <input
                id="detail-file-upload"
                type="file"
                className="hidden"
                multiple
                accept=".pdf,.txt,.csv,.json,.xml,.md,.doc,.docx,.yaml,.yml"
                onChange={handleFileUpload}
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {files.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">No documents uploaded yet</p>
            )}
            {files.map((f, i) => {
              const docRecord = documents.find(d => d.file_name === f.name);
              const isReprocessing = docRecord && reprocessingId === docRecord.id;
              return (
                <div key={i} className="flex items-center justify-between p-2 rounded-md bg-muted/50 text-sm group">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                    <span className="truncate">{f.name}</span>
                    <span className="text-xs text-muted-foreground">({(f.size / 1024).toFixed(1)} KB)</span>
                    {docRecord && statusBadge(docRecord.status)}
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {docRecord?.storage_path && (
                      <>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          title="Preview document"
                          disabled={previewLoading}
                          onClick={async () => {
                            setPreviewLoading(true);
                            setPreviewName(f.name);
                            const { data, error } = await supabase.storage
                              .from("vendor-documents")
                              .createSignedUrl(docRecord.storage_path!, 300);
                            setPreviewLoading(false);
                            if (error || !data?.signedUrl) {
                              toast.error("Failed to load preview");
                              return;
                            }
                            setPreviewUrl(data.signedUrl);
                          }}
                        >
                          <Eye className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          title="Download document"
                          onClick={async () => {
                            const { data, error } = await supabase.storage.from("vendor-documents").download(docRecord.storage_path!);
                            if (error || !data) { toast.error("Download failed"); return; }
                            const url = URL.createObjectURL(data);
                            const a = document.createElement("a");
                            a.href = url; a.download = f.name; a.click();
                            URL.revokeObjectURL(url);
                          }}
                        >
                          <Download className="h-3 w-3" />
                        </Button>
                      </>
                    )}
                    {docRecord && (docRecord.status === "error" || docRecord.status === "ready") && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        title="Re-process document"
                        disabled={!!isReprocessing}
                        onClick={() => reprocessDocument(docRecord.id, f.name)}
                      >
                        <RefreshCw className={`h-3 w-3 ${isReprocessing ? "animate-spin" : ""}`} />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-destructive hover:text-destructive"
                      title="Delete document"
                      onClick={() => {
                        if (docRecord) {
                          setDeleteTarget({ docId: docRecord.id, fileIndex: i, fileName: f.name });
                        } else {
                          onUpdateFiles(files.filter((_, j) => j !== i));
                        }
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <LinkIcon className="h-4 w-4" /> Links ({links.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex gap-2">
              <Input
                placeholder="https://..."
                value={linkInput}
                onChange={(e) => setLinkInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addLink()}
                className="h-8 text-sm"
              />
              <Button variant="outline" size="sm" onClick={addLink}>
                <Plus className="h-3 w-3" />
              </Button>
            </div>
            {links.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">No links added yet</p>
            )}
            {links.map((l, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-md bg-muted/50 text-sm group">
                {editingLink === i ? (
                  <div className="flex gap-1 flex-1 mr-2">
                    <Input value={editLinkValue} onChange={(e) => setEditLinkValue(e.target.value)} className="h-7 text-xs" onKeyDown={(e) => e.key === "Enter" && saveEditLink()} />
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={saveEditLink}><Check className="h-3 w-3" /></Button>
                  </div>
                ) : (
                  <>
                    <a href={l} target="_blank" rel="noopener noreferrer" className="truncate text-accent hover:underline">{l}</a>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => startEditLink(i)}><Pencil className="h-3 w-3" /></Button>
                      <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => removeLink(i)}><X className="h-3 w-3" /></Button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Delete confirmation dialog */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure you want to delete?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete <strong>{deleteTarget?.fileName}</strong> and all its indexed chunks. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Document preview dialog */}
      <Dialog open={!!previewUrl} onOpenChange={(open) => !open && setPreviewUrl(null)}>
        <DialogContent className="max-w-4xl w-[90vw] h-[85vh] flex flex-col p-0">
          <DialogHeader className="p-4 pb-2">
            <DialogTitle className="text-sm truncate">{previewName}</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 p-4 pt-0">
            <iframe
              src={previewUrl || ""}
              className="w-full h-full rounded-md border"
              title={previewName}
            />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
