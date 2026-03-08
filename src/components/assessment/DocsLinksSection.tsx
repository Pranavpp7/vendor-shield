import { useState } from "react";
import { UploadedFile } from "@/types/assessment";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Link as LinkIcon, Plus, X, Pencil, Check, Upload } from "lucide-react";

type Props = {
  files: UploadedFile[];
  links: string[];
  onUpdateFiles: (files: UploadedFile[]) => void;
  onUpdateLinks: (links: string[]) => void;
};

export function DocsLinksSection({ files, links, onUpdateFiles, onUpdateLinks }: Props) {
  const [linkInput, setLinkInput] = useState("");
  const [editingLink, setEditingLink] = useState<number | null>(null);
  const [editLinkValue, setEditLinkValue] = useState("");

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

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files).map((f) => ({ name: f.name, size: f.size }));
    onUpdateFiles([...files, ...selected]);
  };

  const removeFile = (i: number) => onUpdateFiles(files.filter((_, j) => j !== i));

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
              onClick={() => document.getElementById("detail-file-upload")?.click()}
            >
              <Upload className="h-3 w-3 mr-1" /> Upload
            </Button>
            <input
              id="detail-file-upload"
              type="file"
              className="hidden"
              multiple
              onChange={handleFileInput}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {files.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">No documents uploaded yet</p>
          )}
          {files.map((f, i) => (
            <div key={i} className="flex items-center justify-between p-2 rounded-md bg-muted/50 text-sm group">
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                <span className="truncate">{f.name}</span>
                <span className="text-xs text-muted-foreground">({(f.size / 1024).toFixed(1)} KB)</span>
              </div>
              <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => removeFile(i)}>
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
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
