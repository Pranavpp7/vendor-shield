import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { Assessment } from "@/types/assessment";
import { mockAssessments } from "@/data/mockData";

type AssessmentContextType = {
  assessments: Assessment[];
  addAssessment: (a: Assessment) => void;
  updateAssessment: (id: string, updates: Partial<Assessment>) => void;
  getAssessment: (id: string) => Assessment | undefined;
};

const AssessmentContext = createContext<AssessmentContextType | null>(null);

export function AssessmentProvider({ children }: { children: ReactNode }) {
  const [assessments, setAssessments] = useState<Assessment[]>(() => {
    try {
      const stored = localStorage.getItem("vendor-assessments");
      return stored ? JSON.parse(stored) : mockAssessments;
    } catch {
      return mockAssessments;
    }
  });

  useEffect(() => {
    localStorage.setItem("vendor-assessments", JSON.stringify(assessments));
  }, [assessments]);

  const addAssessment = (a: Assessment) => setAssessments((prev) => [...prev, a]);

  const updateAssessment = (id: string, updates: Partial<Assessment>) => {
    setAssessments((prev) =>
      prev.map((a) => (a.id === id ? { ...a, ...updates } : a))
    );
  };

  const getAssessment = (id: string) => assessments.find((a) => a.id === id);

  return (
    <AssessmentContext.Provider value={{ assessments, addAssessment, updateAssessment, getAssessment }}>
      {children}
    </AssessmentContext.Provider>
  );
}

export const useAssessments = () => {
  const ctx = useContext(AssessmentContext);
  if (!ctx) throw new Error("useAssessments must be used within AssessmentProvider");
  return ctx;
};
