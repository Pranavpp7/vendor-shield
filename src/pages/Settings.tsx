import { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { useChecklistSchema, ChecklistCategory, ChecklistControl } from "@/hooks/useChecklistSchema";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Plus, Trash2, GripVertical, Pencil, Check, X, Save, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Settings() {
  const { schema, loading, saving, saveSchema } = useChecklistSchema();
  const [draft, setDraft] = useState<ChecklistCategory[] | null>(null);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newControlInputs, setNewControlInputs] = useState<Record<string, string>>({});
  const [editingCategory, setEditingCategory] = useState<string | null>(null);
  const [editCategoryName, setEditCategoryName] = useState("");
  const [editingControl, setEditingControl] = useState<string | null>(null);
  const [editControlName, setEditControlName] = useState("");

  const current = draft ?? schema;

  const makeDraft = () => {
    if (!draft) setDraft(JSON.parse(JSON.stringify(schema)));
  };

  const addCategory = () => {
    const name = newCategoryName.trim();
    if (!name) return;
    makeDraft();
    setDraft((prev) => {
      const list = prev ?? JSON.parse(JSON.stringify(schema));
      return [...list, { category: name, controls: [] }];
    });
    setNewCategoryName("");
  };

  const deleteCategory = (catIdx: number) => {
    makeDraft();
    setDraft((prev) => {
      const list = [...(prev ?? JSON.parse(JSON.stringify(schema)))];
      list.splice(catIdx, 1);
      return list;
    });
  };

  const startEditCategory = (catIdx: number) => {
    setEditingCategory(`cat-${catIdx}`);
    setEditCategoryName(current[catIdx].category);
  };

  const confirmEditCategory = (catIdx: number) => {
    const name = editCategoryName.trim();
    if (!name) return;
    makeDraft();
    setDraft((prev) => {
      const list = [...(prev ?? JSON.parse(JSON.stringify(schema)))];
      list[catIdx] = { ...list[catIdx], category: name };
      return list;
    });
    setEditingCategory(null);
  };

  const addControl = (catIdx: number) => {
    const key = `cat-${catIdx}`;
    const name = (newControlInputs[key] ?? "").trim();
    if (!name) return;
    makeDraft();
    setDraft((prev) => {
      const list = [...(prev ?? JSON.parse(JSON.stringify(schema)))];
      const cat = { ...list[catIdx], controls: [...list[catIdx].controls] };
      const id = `${cat.category.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 4)}-${Date.now()}`;
      cat.controls.push({ id, name });
      list[catIdx] = cat;
      return list;
    });
    setNewControlInputs((p) => ({ ...p, [key]: "" }));
  };

  const deleteControl = (catIdx: number, ctrlIdx: number) => {
    makeDraft();
    setDraft((prev) => {
      const list = [...(prev ?? JSON.parse(JSON.stringify(schema)))];
      const cat = { ...list[catIdx], controls: [...list[catIdx].controls] };
      cat.controls.splice(ctrlIdx, 1);
      list[catIdx] = cat;
      return list;
    });
  };

  const startEditControl = (controlId: string, name: string) => {
    setEditingControl(controlId);
    setEditControlName(name);
  };

  const confirmEditControl = (catIdx: number, ctrlIdx: number) => {
    const name = editControlName.trim();
    if (!name) return;
    makeDraft();
    setDraft((prev) => {
      const list = [...(prev ?? JSON.parse(JSON.stringify(schema)))];
      const cat = { ...list[catIdx], controls: [...list[catIdx].controls] };
      cat.controls[ctrlIdx] = { ...cat.controls[ctrlIdx], name };
      list[catIdx] = cat;
      return list;
    });
    setEditingControl(null);
  };

  const handleSave = async () => {
    if (!draft) return;
    await saveSchema(draft);
    setDraft(null);
    toast.success("Checklist schema saved successfully.");
  };

  const handleDiscard = () => {
    setDraft(null);
    toast.info("Changes discarded.");
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Settings</h1>
            <p className="text-sm text-muted-foreground">Manage your assessment checklist template</p>
          </div>
          {draft && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleDiscard}>
                <X className="h-3.5 w-3.5 mr-1" /> Discard
              </Button>
              <Button size="sm" onClick={handleSave} disabled={saving}>
                {saving ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Save className="h-3.5 w-3.5 mr-1" />}
                Save Changes
              </Button>
            </div>
          )}
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Checklist Sections & Controls</CardTitle>
            <CardDescription>
              Add, edit, or remove checklist sections and their items. Changes apply to all future assessments.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Accordion type="multiple" defaultValue={current.map((_, i) => `section-${i}`)} className="space-y-2">
              {current.map((cat, catIdx) => (
                <AccordionItem key={`section-${catIdx}`} value={`section-${catIdx}`} className="border rounded-lg px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <GripVertical className="h-4 w-4 text-muted-foreground/50 flex-shrink-0" />
                      {editingCategory === `cat-${catIdx}` ? (
                        <div className="flex items-center gap-1.5 flex-1" onClick={(e) => e.stopPropagation()}>
                          <Input
                            value={editCategoryName}
                            onChange={(e) => setEditCategoryName(e.target.value)}
                            className="h-7 text-sm"
                            onKeyDown={(e) => e.key === "Enter" && confirmEditCategory(catIdx)}
                            autoFocus
                          />
                          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => confirmEditCategory(catIdx)}>
                            <Check className="h-3.5 w-3.5 text-risk-low" />
                          </Button>
                          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditingCategory(null)}>
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 flex-1">
                          <span className="font-semibold text-sm">{cat.category}</span>
                          <span className="text-xs text-muted-foreground">({cat.controls.length} items)</span>
                        </div>
                      )}
                      {editingCategory !== `cat-${catIdx}` && (
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => startEditCategory(catIdx)}>
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => deleteCategory(catIdx)}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-1.5 pt-1">
                      {cat.controls.map((ctrl, ctrlIdx) => (
                        <div key={ctrl.id} className="flex items-center gap-2 group px-2 py-1.5 rounded hover:bg-muted/50 transition-colors">
                          <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40 flex-shrink-0" />
                          {editingControl === ctrl.id ? (
                            <div className="flex items-center gap-1.5 flex-1">
                              <Input
                                value={editControlName}
                                onChange={(e) => setEditControlName(e.target.value)}
                                className="h-7 text-sm"
                                onKeyDown={(e) => e.key === "Enter" && confirmEditControl(catIdx, ctrlIdx)}
                                autoFocus
                              />
                              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => confirmEditControl(catIdx, ctrlIdx)}>
                                <Check className="h-3.5 w-3.5 text-risk-low" />
                              </Button>
                              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditingControl(null)}>
                                <X className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          ) : (
                            <>
                              <span className="text-sm flex-1">{ctrl.name}</span>
                              <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => startEditControl(ctrl.id, ctrl.name)}>
                                  <Pencil className="h-3 w-3" />
                                </Button>
                                <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive hover:text-destructive" onClick={() => deleteControl(catIdx, ctrlIdx)}>
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </>
                          )}
                        </div>
                      ))}
                      <div className="flex items-center gap-2 pt-2">
                        <Input
                          placeholder="New checklist item…"
                          value={newControlInputs[`cat-${catIdx}`] ?? ""}
                          onChange={(e) => setNewControlInputs((p) => ({ ...p, [`cat-${catIdx}`]: e.target.value }))}
                          className="h-8 text-sm"
                          onKeyDown={(e) => e.key === "Enter" && addControl(catIdx)}
                        />
                        <Button size="sm" variant="outline" className="h-8" onClick={() => addControl(catIdx)}>
                          <Plus className="h-3.5 w-3.5 mr-1" /> Add
                        </Button>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>

            <Separator />

            <div className="flex items-center gap-2">
              <Input
                placeholder="New section name…"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                className="h-9"
                onKeyDown={(e) => e.key === "Enter" && addCategory()}
              />
              <Button variant="outline" onClick={addCategory}>
                <Plus className="h-4 w-4 mr-1.5" /> Add Section
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
