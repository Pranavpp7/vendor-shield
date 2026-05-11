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
import { FileText, Link as LinkIcon, Globe, Plus, X, Pencil, Check, Upload, Loader2, CheckCircle, AlertCircle, RefreshCw, Trash2 } from "lucide-react";
import { IndexingPipelineFlow } from "./IndexingPipelineFlow";
import { toast } from "sonner";
import { deleteDocument, fetchDocuments } from "@/lib/api";

type DocumentRecord = {
  id: string;
  file_name: string;
  file_size: number;
  status: string;
  storage_path: string | null;
  created_at: string;
  source_type?: string;
  source_url?: string;
  chunks_created?: number;
};

type Props = {
  files: UploadedFile[];
  links: string[];
  onUpdateFiles: (files: UploadedFile[]) => void;
  onUpdateLinks: (links: string[]) => void;
  assessmentId?: string;
  vendorName?: string;
  onRerunChecklist?: () => void;
  highlightDoc?: string | null;
  onClearHighlight?: () => void;
};

export function DocsLinksSection({ files, links, onUpdateFiles, onUpdateLinks, assessmentId, vendorName, onRerunChecklist, highlightDoc, onClearHighlight }: Props) {
  const [linkInput, setLinkInput] = useState("");
  const [editingLink, setEditingLink] = useState<number | null>(null);
  const [editLinkValue, setEditLinkValue] = useState("");
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ docId: string; fileName: string } | null>(null);
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);
  const fileRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const loadSeqRef = useRef(0);

  // Handle highlight from evidence source click
  useEffect(() => {
    if (!highlightDoc) return;
    // Skip non-file evidence sources
    const skip = ["no evidence found", "no documents uploaded", "service unavailable", "parse error"];
    if (skip.some(s => highlightDoc.toLowerCase().includes(s))) {
      onClearHighlight?.();
      return;
    }
    
    const hl = highlightDoc.toLowerCase();
    const idx = files.findIndex(f => {
      const fName = f.name.toLowerCase();
      // Match if either contains the other, or if the evidence source filename (without extension) matches
      const hlBase = hl.replace(/\.[^.]+$/, "");
      const fBase = fName.replace(/\.[^.]+$/, "");
      return fName.includes(hl) || hl.includes(fName) || fBase.includes(hlBase) || hlBase.includes(fBase);
    });
    
    if (idx !== -1) {
      setHighlightedIndex(idx);
      const scrollTimer = setTimeout(() => {
        fileRefs.current.get(idx)?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 300);
      const clearTimer = setTimeout(() => {
        setHighlightedIndex(null);
        onClearHighlight?.();
      }, 3000);
      return () => { clearTimeout(scrollTimer); clearTimeout(clearTimer); };
    } else {
      // No match found - still highlight nothing but don't clear immediately
      // so the tab switch still works
      onClearHighlight?.();
    }
  }, [highlightDoc, files]);

  useEffect(() => {
    if (!assessmentId) return;
    loadDocuments();
  }, [assessmentId]);

  const loadDocuments = async () => {
    if (!assessmentId) return;

    const requestSeq = ++loadSeqRef.current;
    try {
      const docs = await fetchDocuments(assessmentId);
      if (requestSeq !== loadSeqRef.current) return;

      const typed: DocumentRecord[] = docs.map((d: any) => ({
        id: d.id,
        file_name: d.file_name || d.filename || "Unknown",
        file_size: d.file_size || 0,
        status: d.status || "ready",
        storage_path: null,
        created_at: d.created_at || new Date().toISOString(),
        source_type: d.source_url ? "url" : "file",
        source_url: d.source_url || null,
        chunks_created: d.chunks_created || 0,
      }));

      setDocuments((prev) => {
        const unresolvedOptimistic = prev.filter(
          (doc) =>
            doc.id.startsWith("temp-") &&
            !typed.some(
              (serverDoc) =>
                serverDoc.file_name === doc.file_name &&
                (serverDoc.file_size || 0) === (doc.file_size || 0)
            )
        );
        return [...unresolvedOptimistic, ...typed].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
      });

      onUpdateFiles(typed.map((d) => ({ name: d.file_name, size: d.file_size || 0 })));
    } catch (err) {
      console.error("Failed to load documents:", err);
    }
  };


  useEffect(() => {
    const processing = documents.some(d => d.status === "pending" || d.status === "processing");
    if (!processing) return;
    const interval = setInterval(loadDocuments, 3000);
    return () => clearInterval(interval);
  }, [documents]);

  const addLink = async () => {
    const url = linkInput.trim();
    if (!url) return;
    setLinkInput("");

    if (assessmentId) {
      // Submit to FastAPI ingest-url endpoint
      toast.info(`Submitting ${url} for indexing…`);
      try {
        const { ingestUrl } = await import("@/lib/api");
        await ingestUrl(url, assessmentId, vendorName || "Unknown Vendor");
        toast.success(`URL submitted for indexing`);
        loadDocuments();
      } catch (err: any) {
        console.error("ingest-url error:", err);
        toast.error(`Failed to index URL: ${err.message}`);
      }
    } else {
      // Pre-creation: just store in local links array
      onUpdateLinks([...links, url]);
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

    // Optimistically show every selected file immediately in the UI
    const now = new Date().toISOString();
    const optimisticDocs: DocumentRecord[] = selectedFiles.map((file) => ({
      id: `temp-${crypto.randomUUID()}`,
      file_name: file.name,
      file_size: file.size,
      status: "pending",
      storage_path: null,
      created_at: now,
      chunks_created: 0,
    }));
    const optimisticIds = new Set(optimisticDocs.map((d) => d.id));
    setDocuments((prev) => [...optimisticDocs, ...prev]);

    // Upload each file via FastAPI /api/documents/upload
    const { ingestDocument } = await import("@/lib/api");
    const uploadResults = await Promise.all(selectedFiles.map(async (file) => {
      try {
        const result = await ingestDocument(file, assessmentId, vendorName || "Unknown Vendor");
        toast.success(`Uploaded ${file.name}`);
        return {
          id: result.document_id,
          file_name: file.name,
          file_size: file.size,
          status: result.status || "ready",
          storage_path: null,
          created_at: now,
          chunks_created: result.chunks_created || 0,
        } as DocumentRecord;
      } catch (err: any) {
        console.error("Upload error:", err);
        toast.error(`Failed to upload ${file.name}: ${err.message}`);
        return null;
      }
    }));

    const insertedDocs = uploadResults.filter((doc): doc is DocumentRecord => doc !== null);
    setDocuments((prev) => {
      const withoutOptimistic = prev.filter((d) => !optimisticIds.has(d.id));
      const merged = [...insertedDocs, ...withoutOptimistic];
      const byId = new Map(merged.map((d) => [d.id, d]));
      return Array.from(byId.values()).sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    });

    setUploading(false);
    await loadDocuments();
    e.target.value = "";
  };

  const reprocessDocument = async (doc: DocumentRecord) => {
    setReprocessingId(doc.id);
    try {
      if (doc.source_type === "url" && doc.source_url) {
        // For URL docs, delete via FastAPI and re-ingest
        await deleteDocument(doc.id, assessmentId || "");
        const { ingestUrl } = await import("@/lib/api");
        await ingestUrl(doc.source_url, assessmentId || "", vendorName || "Unknown Vendor");
        toast.success(`Re-processing ${doc.source_url}`);
      } else {
        // For file docs, delete and notify user to re-upload
        await deleteDocument(doc.id, assessmentId || "");
        toast.info(`Deleted ${doc.file_name}. Please re-upload to re-process.`);
      }
    } catch (err: any) {
      console.error("Reprocess error:", err);
      toast.error(`Failed to re-process: ${err.message}`);
    } finally {
      setReprocessingId(null);
      loadDocuments();
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget || !assessmentId) return;
    try {
      await deleteDocument(deleteTarget.docId, assessmentId);
      
      toast.success(`Deleted ${deleteTarget.fileName}`);
      await loadDocuments();
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
        return <Badge variant="outline" className="text-[10px] gap-1 text-accent border-accent/30"><Loader2 className="h-2.5 w-2.5 animate-spin" />Processing</Badge>;
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
                <FileText className="h-4 w-4" />
                {(() => {
                  const fileDocs = assessmentId ? documents.filter(d => d.source_type !== 'url') : [];
                  const totalChunks = fileDocs.reduce((sum, d) => sum + (d.chunks_created || 0), 0);
                  const count = assessmentId ? fileDocs.length : files.length;
                  return (
                    <>
                      Documents ({count})
                      {assessmentId && totalChunks > 0 && (
                        <span className="text-xs font-normal text-muted-foreground">
                          · {totalChunks} {totalChunks === 1 ? "chunk" : "chunks"} indexed
                        </span>
                      )}
                    </>
                  );
                })()}
              </CardTitle>
              {assessmentId && documents.length > 0 && (
                <IndexingPipelineFlow assessmentId={assessmentId} documents={documents.map(d => ({ id: d.id, file_name: d.file_name, status: d.status }))} />
              )}
              <Button
                variant="outline"
                size="sm"
                disabled={uploading}
                onClick={() => uploadInputRef.current?.click()}
              >
                {uploading ? (
                  <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Uploading…</>
                ) : (
                  <><Upload className="h-3 w-3 mr-1" /> Upload</>
                )}
              </Button>
              <input
                ref={uploadInputRef}
                type="file"
                className="hidden"
                multiple
                accept=".pdf,.txt,.csv,.json,.xml,.md,.doc,.docx,.yaml,.yml"
                onChange={handleFileUpload}
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {(assessmentId ? documents.filter(d => d.source_type !== 'url').length === 0 : files.length === 0) && (
              <p className="text-xs text-muted-foreground text-center py-4">No documents uploaded yet</p>
            )}

            {assessmentId ? (
              documents.filter(d => d.source_type !== 'url').map((doc, i) => {
                const isReprocessing = reprocessingId === doc.id;
                return (
                  <div key={doc.id} ref={(el) => { if (el) fileRefs.current.set(i, el); else fileRefs.current.delete(i); }} className={`flex items-center justify-between p-2 rounded-md text-sm group transition-all duration-500 ${highlightedIndex === i ? "bg-accent/20 ring-2 ring-accent/40" : "bg-muted/50"}`}>
                    <div className="flex items-center gap-2 min-w-0">
                      {doc.source_type === "url" ? (
                        <Globe className="h-3.5 w-3.5 text-accent flex-shrink-0" />
                      ) : (
                        <FileText className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                      )}
                      {doc.source_type === "url" && doc.source_url ? (
                        <a href={doc.source_url} target="_blank" rel="noopener noreferrer" className="truncate text-accent hover:underline text-xs">{doc.file_name}</a>
                      ) : (
                        <span className="truncate">{doc.file_name}</span>
                      )}
                      {doc.source_type !== "url" && (
                        <span className="text-xs text-muted-foreground">
                          ({((doc.file_size || 0) / 1024).toFixed(1)} KB
                          {doc.chunks_created ? ` · ${doc.chunks_created} chunks` : ""})
                        </span>
                      )}
                      {doc.created_at && (
                        <span className="text-[10px] text-muted-foreground/70" title={new Date(doc.created_at).toLocaleString()}>
                          {new Date(doc.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}{' '}
                          {new Date(doc.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                      {statusBadge(doc.status)}
                    </div>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {(doc.status === "error" || doc.status === "ready") && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          title="Re-process document"
                          disabled={!!isReprocessing}
                          onClick={() => reprocessDocument(doc)}
                        >
                          <RefreshCw className={`h-3 w-3 ${isReprocessing ? "animate-spin" : ""}`} />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-destructive hover:text-destructive"
                        title="Delete document"
                        onClick={() => setDeleteTarget({ docId: doc.id, fileName: doc.file_name })}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                );
              })
            ) : (
              files.map((f, i) => (
                <div key={`${f.name}-${i}`} className="flex items-center justify-between p-2 rounded-md bg-muted/50 text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                    <span className="truncate">{f.name}</span>
                    <span className="text-xs text-muted-foreground">({(f.size / 1024).toFixed(1)} KB)</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-destructive hover:text-destructive"
                    title="Delete document"
                    onClick={() => onUpdateFiles(files.filter((_, j) => j !== i))}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <LinkIcon className="h-4 w-4" /> Links ({assessmentId ? documents.filter(d => d.source_type === "url").length : links.length})
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
            {(() => {
              const urlDocs = assessmentId ? documents.filter(d => d.source_type === "url") : [];
              const allLinks = assessmentId ? urlDocs : links.map((l, i) => ({ url: l, index: i }));
              
              if (allLinks.length === 0) {
                return <p className="text-xs text-muted-foreground text-center py-4">No links added yet</p>;
              }

              if (assessmentId) {
                return urlDocs.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between p-2 rounded-md bg-muted/50 text-sm group">
                    <div className="flex items-center gap-2 min-w-0">
                      <Globe className="h-3.5 w-3.5 text-accent flex-shrink-0" />
                      <a href={doc.source_url || "#"} target="_blank" rel="noopener noreferrer" className="truncate text-accent hover:underline text-xs">{doc.source_url || doc.file_name}</a>
                      {statusBadge(doc.status)}
                    </div>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {(doc.status === "error" || doc.status === "ready") && (
                        <Button variant="ghost" size="icon" className="h-6 w-6" title="Re-index" disabled={reprocessingId === doc.id} onClick={() => reprocessDocument(doc)}>
                          <RefreshCw className={`h-3 w-3 ${reprocessingId === doc.id ? "animate-spin" : ""}`} />
                        </Button>
                      )}
                      <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive hover:text-destructive" title="Delete" onClick={() => setDeleteTarget({ docId: doc.id, fileName: doc.file_name })}>
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ));
              }

              return links.map((l, i) => (
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
              ));
            })()}
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

    </div>
  );
}
