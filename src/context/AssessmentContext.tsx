import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { Assessment } from "@/types/assessment";
import { vendorNameToSlug } from "@/lib/utils";
import {
  deleteAssessment as deleteAssessmentAPI,
  fetchAssessments as fetchAssessmentsAPI,
  updateAssessmentPartial,
} from "@/lib/api";

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

export function AssessmentProvider({ children }: { children: ReactNode }) {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAssessments = useCallback(async () => {
    setLoading(true);
    try {
      setAssessments(await fetchAssessmentsAPI());
    } catch (err) {
      console.error("Failed to fetch assessments:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAssessments();
  }, [fetchAssessments]);

  const addAssessment = async (a: Assessment) => {
    setAssessments((prev) => [a, ...prev.filter((x) => x.id !== a.id)]);
  };

  const updateAssessment = async (id: string, updates: Partial<Assessment>) => {
    // Update local state immediately for snappy UI
    setAssessments((prev) =>
      prev.map((a) => (a.id === id ? { ...a, ...updates } : a))
    );

    // Persist notes and chatHistory to backend
    const body: Record<string, unknown> = {};
    if ("notes" in updates) body.notes = updates.notes;
    if ("chatHistory" in updates) body.chat_history = updates.chatHistory;

    if (Object.keys(body).length > 0) {
      try {
        await updateAssessmentPartial(id, body);
      } catch (err) {
        console.error("Failed to persist assessment update:", err);
      }
    }
  };

  const deleteAssessment = async (id: string) => {
    try {
      await deleteAssessmentAPI(id);
      setAssessments((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      console.error("Failed to delete assessment:", err);
    }
  };

  const getAssessment = (id: string) => assessments.find((a) => a.id === id);

  const getAssessmentBySlug = (slug: string) =>
    assessments.find((a) => a.id === slug || vendorNameToSlug(a.vendorName) === slug);

  return (
    <AssessmentContext.Provider
      value={{
        assessments,
        loading,
        addAssessment,
        updateAssessment,
        deleteAssessment,
        getAssessment,
        getAssessmentBySlug,
        refreshAssessments: fetchAssessments,
      }}
    >
      {children}
    </AssessmentContext.Provider>
  );
}

export const useAssessments = () => {
  const ctx = useContext(AssessmentContext);
  if (!ctx) throw new Error("useAssessments must be used within AssessmentProvider");
  return ctx;
};
