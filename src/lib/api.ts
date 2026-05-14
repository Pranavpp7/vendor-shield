// Always use relative URLs. In dev the Vite proxy forwards /api/* and /mcp
// to http://localhost:8000. In production FastAPI serves everything.
const API_BASE = "";

type TokenGetter = () => Promise<string | null>;
let _getToken: TokenGetter | null = null;

export function setTokenGetter(fn: TokenGetter): void {
  _getToken = fn;
}

export const apiFetch = async (input: string, init: RequestInit = {}): Promise<Response> => {
  const token = _getToken ? await _getToken() : null;
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  return fetch(input, {
    ...init,
    headers: {
      ...authHeaders,
      ...(init.headers || {}),
    },
  });
};

import { mapBackendAssessment, mapControl, mapDomainScores } from "@/lib/mappers";
import { Assessment } from "@/types/assessment";

export async function generateChecklistFromAI(
  vendorName: string,
  controls: { id: string; category: string; name: string }[],
  assessmentId?: string
) {
  try {
    const response = await apiFetch(`${API_BASE}/api/assessments/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vendor_name: vendorName,
        assessment_id: assessmentId || "",
      }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();
    const rawControls: any[] = data.control_results || [];

    return {
      controls: rawControls.map(mapControl),
      score: data.overall_score,
      riskLevel: data.risk_level,
      domainScores: mapDomainScores(data.domain_scores, rawControls),
      summary: data.summary,
      gapsSummary: data.gaps_summary,
    };
  } catch (err) {
    console.error("Checklist generation failed:", err);
    const fallbackControls = controls.map((c) => ({
      ...c,
      passed: false,
      status: "needs_info" as const,
      comment: "",
      aiExplanation: "Unable to connect to backend. Please ensure the FastAPI server is running on port 8000.",
      evidenceSource: "Service unavailable",
    }));
    return {
      controls: fallbackControls,
      score: 0,
      riskLevel: "High",
    };
  }
}

export async function chatWithAI(
  question: string,
  checklistJson: string,
  assessmentId?: string
): Promise<{ reply: string; sources: { document: string; excerpt: string; similarity?: number }[] }> {
  try {
    const response = await apiFetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        assessment_id: assessmentId || "",
        context: checklistJson,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Chat API error ${response.status}:`, errorText);
      throw new Error(`API error: ${response.status}`);
    }
    const data = await response.json();
    return { reply: data.reply, sources: data.sources ?? [] };
  } catch (error) {
    console.error("Chat error:", error);
    return {
      reply: "Unable to connect to backend. Please ensure the FastAPI server is running on port 8000.",
      sources: [],
    };
  }
}

export async function generateSummaryFromAI(
  vendorName: string,
  score: number,
  riskLevel: string,
  controls: any[],
  notes: string,
  assessmentId?: string
): Promise<string> {
  try {
    const response = await apiFetch(`${API_BASE}/api/chat/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vendor_name: vendorName,
        assessment_id: assessmentId || "",
        score,
        risk_level: riskLevel,
        controls,
        notes,
      }),
    });

    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    return data.summary;
  } catch {
    const failed = controls.filter((c: any) => !c.passed).length;
    return `## Vendor Risk Summary: ${vendorName}\n\n**Overall Score:** ${score}/100 | **Risk Level:** ${riskLevel}\n\nEvaluated ${controls.length} controls. ${failed} controls did not meet requirements.\n\n${notes ? `**Analyst Notes:** ${notes}` : "No analyst notes recorded."}`;
  }
}

export async function ingestDocument(
  file: File,
  assessmentId: string,
  vendorName: string,
): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("assessment_id", assessmentId);
  formData.append("vendor_name", vendorName);

  const response = await apiFetch(`${API_BASE}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) throw new Error(`Upload failed: ${response.status}`);
  return response.json();
}

export async function ingestUrl(
  url: string,
  assessmentId: string,
  vendorName: string
): Promise<any> {
  const response = await apiFetch(`${API_BASE}/api/documents/ingest-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      assessment_id: assessmentId,
      vendor_name: vendorName,
    }),
  });

  if (!response.ok) throw new Error(`URL ingestion failed: ${response.status}`);
  return response.json();
}

export async function deleteDocument(documentId: string, assessmentId: string): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/documents/${documentId}?assessment_id=${assessmentId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Delete failed: ${response.status}`);
  }
}

export async function deleteAssessment(assessmentId: string): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/assessments/${assessmentId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Delete failed: ${response.status}`);
  }
}

export async function fetchAssessments(): Promise<Assessment[]> {
  const response = await apiFetch(`${API_BASE}/api/assessments`);
  if (!response.ok) {
    throw new Error(`Failed to fetch assessments: ${response.status}`);
  }
  const data = await response.json();
  return (data.assessments || []).map(mapBackendAssessment);
}

export async function fetchAssessmentDetail(id: string): Promise<Assessment> {
  const response = await apiFetch(`${API_BASE}/api/assessments/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch assessment: ${response.status}`);
  }
  const data = await response.json();
  return mapBackendAssessment(data);
}

export async function updateAssessmentPartial(
  assessmentId: string,
  updates: Record<string, unknown>
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/assessments/${assessmentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!response.ok) {
    throw new Error(`Failed to update assessment: ${response.status}`);
  }
}

export async function fetchDocuments(assessmentId: string): Promise<any[]> {
  const response = await apiFetch(`${API_BASE}/api/documents/${assessmentId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch documents: ${response.status}`);
  }
  const data = await response.json();
  return data.documents || [];
}

export type VendorHistoryEntry = {
  id: string;
  score: number;
  domain_scores: Record<string, number>;
  created_at: string;
};

export async function fetchVendorHistory(vendorName: string): Promise<VendorHistoryEntry[]> {
  const encoded = encodeURIComponent(vendorName);
  const response = await apiFetch(`${API_BASE}/api/vendors/${encoded}/history`);
  if (!response.ok) {
    throw new Error(`Failed to fetch vendor history: ${response.status}`);
  }
  const data = await response.json();
  return data.history || [];
}

export async function fetchCompareAssessments(ids: [string, string]): Promise<any[]> {
  const qs = `${encodeURIComponent(ids[0])},${encodeURIComponent(ids[1])}`;
  const response = await apiFetch(`${API_BASE}/api/assessments/compare?ids=${qs}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch comparison: ${response.status} ${text}`);
  }
  const data = await response.json();
  return data.assessments || [];
}
