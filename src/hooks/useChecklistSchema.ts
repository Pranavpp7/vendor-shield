import { useState, useCallback } from "react";
import { checklistSchema as defaultSchema } from "@/data/checklistSchema";

export type ChecklistControl = { id: string; name: string };
export type ChecklistCategory = { category: string; controls: ChecklistControl[] };

export function useChecklistSchema() {
  const [schema, setSchema] = useState<ChecklistCategory[]>(defaultSchema);
  const [saving, setSaving] = useState(false);

  // Schema customisation previously persisted to Supabase per-user.
  // With auth removed, changes are local to the session only.
  const saveSchema = useCallback(async (newSchema: ChecklistCategory[]) => {
    setSaving(true);
    setSchema(newSchema);
    setSaving(false);
  }, []);

  const allControls = schema.flatMap((g) =>
    g.controls.map((c) => ({ id: c.id, category: g.category, name: c.name }))
  );

  return { schema, loading: false, saving, saveSchema, allControls };
}
