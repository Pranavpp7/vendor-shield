// When served from FastAPI (production), use relative URLs (empty string).
// During Vite dev mode, set VITE_API_BASE_URL=http://localhost:8000 in .env
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export async function generateChecklistFromAI(
  vendorName: string,
  controls: { id: string; category: string; name: string }[],
  assessmentId?: string
) {
  try {
    const response = await fetch(`${API_BASE}/api/assessments/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vendor_name: vendorName,
        assessment_id: assessmentId || "",
        controls: controls.map((c) => ({
          id: c.id,
          name: c.name,
          category: c.category,
          description: "",
          weight: 1.0,
        })),
      }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();

    // Map FastAPI response to frontend format
    const mappedControls = data.control_results.map((r: any) => ({
      id: r.id,
      category: r.category,
      name: r.name,
      passed: r.status === "Pass",
      status: r.status === "Pass" ? "passed" : r.status === "Fail" ? "failed" : r.status === "Partial" ? "partial" : "needs_info",
      comment: "",
      aiExplanation: r.rationale,
      evidenceSource: r.evidence_source || "No evidence found",
      citations: r.citations || [],
    }));

    return {
      controls: mappedControls,
      score: data.overall_score,
      riskLevel: data.risk_level,
      domainScores: data.domain_scores,
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
): Promise<string> {
  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        assessment_id: assessmentId || "",
        context: checklistJson,
      }),
    });

    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    return data.reply;
  } catch {
    return "Unable to connect to backend. Please ensure the FastAPI server is running on port 8000.";
  }
}

export async function generateSummaryFromAI(
  vendorName: string,
  score: number,
  riskLevel: string,
  controls: any[],
  notes: string
): Promise<string> {
  try {
    const response = await fetch(`${API_BASE}/api/chat/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vendor_name: vendorName,
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
  userId?: string
): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("assessment_id", assessmentId);
  formData.append("vendor_name", vendorName);
  if (userId) formData.append("user_id", userId);

  const response = await fetch(`${API_BASE}/api/documents/upload`, {
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
  const response = await fetch(`${API_BASE}/api/documents/ingest-url`, {
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
