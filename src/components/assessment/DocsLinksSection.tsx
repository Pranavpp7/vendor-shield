import { useState, useEffect } from "react";
import { UploadedFile } from "@/types/assessment";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, Link as LinkIcon, Plus, X, Pencil, Check, Upload, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

type DocumentRecord = {
  id: string;
  file_name: string;
  file_size: number;
  status: string;
  created_at: string;
};

type Props = {
  files: UploadedFile[];
  links: string[];
  onUpdateFiles: (files: UploadedFile[]) => void;
  onUpdateLinks: (links: string[]) => void;
  assessmentId?: string;
};

export function DocsLinksSection({ files, links, onUpdateFiles, onUpdateLinks, assessmentId }: Props) {
  const { user } = useAuth();
  const [linkInput, setLinkInput] = useState("");
  const [editingLink, setEditingLink] = useState<number | null>(null);
  const [editLinkValue, setEditLinkValue] = useState("");
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);

  // Load documents from DB
  useEffect(() => {
    if (!assessmentId) return;
    loadDocuments();
  }, [assessmentId]);

  const loadDocuments = async () => {
    if (!assessmentId) return;
    const { data } = await supabase
      .from("documents")
      .select("id, file_name, file_size, status, created_at")
      .eq("assessment_id", assessmentId)
      .order("created_at", { ascending: false });
    if (data) setDocuments(data as DocumentRecord[]);
  };

  // Poll for status changes
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
      // Fallback to local-only if no assessmentId
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

        // Upload to storage
        const { error: uploadErr } = await supabase.storage
          .from("vendor-documents")
          .upload(storagePath, file);

        if (uploadErr) throw uploadErr;

        // Create document record
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

        // Trigger parsing
        supabase.functions.invoke("parse-document", {
          body: { documentId: docRecord.id },
        }).then(() => {
          loadDocuments();
        }).catch((err) => {
          console.error("Parse error:", err);
          loadDocuments();
        });

        // Also update local state
        onUpdateFiles([...files, { name: file.name, size: file.size }]);

        toast.success(`Uploaded ${file.name}`);
      } catch (err: any) {
        console.error("Upload error:", err);
        toast.error(`Failed to upload ${file.name}: ${err.message}`);
      }
    }

    setUploading(false);
    loadDocuments();
    // Reset input
    e.target.value = "";
  };

  const removeFile = async (i: number) => {
    const file = files[i];
    // Try to remove from DB too
    const doc = documents.find(d => d.file_name === file.name);
    if (doc) {
      await supabase.from("documents").delete().eq("id", doc.id);
      loadDocuments();
    }
    onUpdateFiles(files.filter((_, j) => j !== i));
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4" /> Documents ({files.length})
            </CardTitle>
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
            return (
              <div key={i} className="flex items-center justify-between p-2 rounded-md bg-muted/50 text-sm group">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                  <span className="truncate">{f.name}</span>
                  <span className="text-xs text-muted-foreground">({(f.size / 1024).toFixed(1)} KB)</span>
                  {docRecord && statusBadge(docRecord.status)}
                </div>
                <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => removeFile(i)}>
                  <X className="h-3 w-3" />
                </Button>
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
  );
}
