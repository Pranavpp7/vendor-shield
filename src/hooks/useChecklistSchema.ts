import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/context/AuthContext";
import { checklistSchema as defaultSchema } from "@/data/checklistSchema";

export type ChecklistControl = { id: string; name: string };
export type ChecklistCategory = { category: string; controls: ChecklistControl[] };

export function useChecklistSchema() {
  const { user } = useAuth();
  const [schema, setSchema] = useState<ChecklistCategory[]>(defaultSchema);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchSchema = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    const { data } = await supabase
      .from("checklist_schemas")
      .select("schema")
      .eq("user_id", user.id)
      .maybeSingle();

    if (data?.schema) {
      setSchema(data.schema as unknown as ChecklistCategory[]);
    } else {
      setSchema(defaultSchema);
    }
    setLoading(false);
  }, [user]);

  useEffect(() => {
    fetchSchema();
  }, [fetchSchema]);

  const saveSchema = useCallback(
    async (newSchema: ChecklistCategory[]) => {
      if (!user) return;
      setSaving(true);
      // upsert: check if row exists
      const { data: existing } = await supabase
        .from("checklist_schemas")
        .select("id")
        .eq("user_id", user.id)
        .maybeSingle();

      if (existing) {
        await supabase
          .from("checklist_schemas")
          .update({ schema: newSchema as any, updated_at: new Date().toISOString() })
          .eq("user_id", user.id);
      } else {
        await supabase
          .from("checklist_schemas")
          .insert({ user_id: user.id, schema: newSchema as any });
      }
      setSchema(newSchema);
      setSaving(false);
    },
    [user]
  );

  const allControls = schema.flatMap((g) =>
    g.controls.map((c) => ({ id: c.id, category: g.category, name: c.name }))
  );

  return { schema, loading, saving, saveSchema, allControls };
}
