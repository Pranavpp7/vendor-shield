import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { Assessment } from "@/types/assessment";
import { vendorNameToSlug } from "@/lib/utils";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/context/AuthContext";

type AssessmentContextType = {
  assessments: Assessment[];
  loading: boolean;
  addAssessment: (a: Assessment) => Promise<void>;
  updateAssessment: (id: string, updates: Partial<Assessment>) => Promise<void>;
  deleteAssessment: (id: string) => Promise<void>;
  getAssessment: (id: string) => Assessment | undefined;
  getAssessmentBySlug: (slug: string) => Assessment | undefined;
  refreshAssessments: () => Promise<void>;
};

const AssessmentContext = createContext<AssessmentContextType | null>(null);

function dbRowToAssessment(row: any): Assessment {
  return {
    id: row.id,
    vendorName: row.vendor_name,
    criticality: row.criticality,
    createdAt: row.created_at,
    status: row.status,
    score: row.score,
    riskLevel: row.risk_level,
    controls: row.controls || [],
    notes: row.notes || "",
    chatHistory: row.chat_history || [],
    uploadedFiles: row.uploaded_files || [],
    links: row.links || [],
  };
}

function assessmentToDbRow(a: Partial<Assessment> & { id?: string }, userId?: string) {
  const row: any = {};
  if (a.id !== undefined) row.id = a.id;
  if (userId) row.user_id = userId;
  if (a.vendorName !== undefined) row.vendor_name = a.vendorName;
  if (a.criticality !== undefined) row.criticality = a.criticality;
  if (a.createdAt !== undefined) row.created_at = a.createdAt;
  if (a.status !== undefined) row.status = a.status;
  if (a.score !== undefined) row.score = a.score;
  if (a.riskLevel !== undefined) row.risk_level = a.riskLevel;
  if (a.controls !== undefined) row.controls = a.controls;
  if (a.notes !== undefined) row.notes = a.notes;
  if (a.chatHistory !== undefined) row.chat_history = a.chatHistory;
  if (a.uploadedFiles !== undefined) row.uploaded_files = a.uploadedFiles;
  if (a.links !== undefined) row.links = a.links;
  row.updated_at = new Date().toISOString();
  return row;
}

export function AssessmentProvider({ children }: { children: ReactNode }) {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  const fetchAssessments = useCallback(async () => {
    if (!user) {
      setAssessments([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const { data, error } = await supabase
      .from("assessments")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      console.error("Failed to fetch assessments:", error);
    } else {
      setAssessments((data || []).map(dbRowToAssessment));
    }
    setLoading(false);
  }, [user]);

  useEffect(() => {
    fetchAssessments();
  }, [fetchAssessments]);

  const addAssessment = async (a: Assessment) => {
    if (!user) return;
    const row = assessmentToDbRow(a, user.id);
    const { error } = await supabase.from("assessments").insert(row);
    if (error) {
      console.error("Failed to add assessment:", error);
      return;
    }
    setAssessments((prev) => [a, ...prev]);
  };

  const updateAssessment = async (id: string, updates: Partial<Assessment>) => {
    const row = assessmentToDbRow(updates);
    const { error } = await supabase.from("assessments").update(row).eq("id", id);
    if (error) {
      console.error("Failed to update assessment:", error);
      return;
    }
    setAssessments((prev) =>
      prev.map((a) => (a.id === id ? { ...a, ...updates } : a))
    );
  };

  const deleteStorageFilesByPrefix = async (prefix: string) => {
    const storage = supabase.storage.from("vendor-documents");

    while (true) {
      const { data: listed, error: listError } = await storage.list(prefix, { limit: 100 });
      if (listError) throw listError;
      if (!listed || listed.length === 0) break;

      const paths = listed
        .filter((item) => Boolean(item.name))
        .map((item) => `${prefix}/${item.name}`);

      if (paths.length === 0) break;

      const { error: removeError } = await storage.remove(paths);
      if (removeError) throw removeError;

      if (listed.length < 100) break;
    }
  };

  const deleteAssessment = async (id: string) => {
    try {
      // Use the new FastAPI endpoint
      const { deleteAssessment: deleteAssessmentAPI } = await import("@/lib/api");
      await deleteAssessmentAPI(id);
      
      setAssessments((prev) => prev.filter((a) => a.id !== id));
      return;
    } catch (error) {
      console.warn("Server cleanup via FastAPI failed, falling back to client cleanup:", error);

      try {
        // Delete all files in the assessment folder first, including orphaned files
        await deleteStorageFilesByPrefix(id);

        // Get documents to delete chunk records
        const { data: docs, error: docsFetchError } = await supabase
          .from("documents")
          .select("id")
          .eq("assessment_id", id);
        if (docsFetchError) throw docsFetchError;

        if (docs && docs.length > 0) {
          const docIds = docs.map((d) => d.id);
          const { error: chunksDeleteError } = await supabase
            .from("document_chunks")
            .delete()
            .in("document_id", docIds);
          if (chunksDeleteError) throw chunksDeleteError;
        }

        const { error: docsDeleteError } = await supabase
          .from("documents")
          .delete()
          .eq("assessment_id", id);
        if (docsDeleteError) throw docsDeleteError;

        const { error: runsDeleteError } = await supabase
          .from("assessment_runs")
          .delete()
          .eq("assessment_id", id);
        if (runsDeleteError) throw runsDeleteError;

        const { error: assessmentDeleteError } = await supabase
          .from("assessments")
          .delete()
          .eq("id", id);
        if (assessmentDeleteError) throw assessmentDeleteError;

        setAssessments((prev) => prev.filter((a) => a.id !== id));
      } catch (err) {
        console.error("Failed to delete assessment:", err);
      }
    }
  };

  const getAssessment = (id: string) => assessments.find((a) => a.id === id);

  const getAssessmentBySlug = (slug: string) =>
    assessments.find((a) => a.id === slug || vendorNameToSlug(a.vendorName) === slug);

  return (
    <AssessmentContext.Provider value={{ assessments, loading, addAssessment, updateAssessment, deleteAssessment, getAssessment, getAssessmentBySlug, refreshAssessments: fetchAssessments }}>
      {children}
    </AssessmentContext.Provider>
  );
}

export const useAssessments = () => {
  const ctx = useContext(AssessmentContext);
  if (!ctx) throw new Error("useAssessments must be used within AssessmentProvider");
  return ctx;
};
