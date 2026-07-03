export type ControlStatus = "passed" | "failed" | "needs_info" | "partial";

export type Citation = {
  document: string;
  page?: number;
  excerpt: string;
  similarity?: number;
};

/** Raw backend score values (see backend ControlScore enum). */
export type BackendScore = "PASS" | "PARTIAL" | "FAIL" | "NO_EVIDENCE";

export type ControlResult = {
  id: string;
  category: string;
  name: string;
  passed: boolean;
  status: ControlStatus;
  comment: string;
  aiExplanation?: string;
  evidenceSource?: string;
  citations?: Citation[];
  confidence?: number;
  gap?: string | null;
  /** The AI's original score (audit trail — never changes on override). */
  aiScore?: BackendScore;
  /** Analyst override; when set it supersedes aiScore everywhere. */
  analystScore?: BackendScore | null;
  analystComment?: string | null;
  overriddenAt?: string | null;
  /** True when AI confidence is low and no analyst has reviewed it yet. */
  needsReview?: boolean;
};

export type FrameworkSummary = {
  id: string;
  name: string;
  description: string;
  version: string;
  control_count: number;
  domains: string[];
};

export type RiskProfile = {
  data_sensitivity: "low" | "moderate" | "high";
  business_criticality: "low" | "moderate" | "high";
  access_scope: "low" | "moderate" | "high";
};

export type FollowUpQuestion = {
  control_id: string;
  domain: string;
  question: string;
  rationale: string;
};

export type EvidenceFreshness = {
  threshold_days: number;
  stale_count: number;
  documents: {
    document_id: string;
    file_name: string;
    uploaded_at: string;
    age_days: number | null;
    stale: boolean;
  }[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  sources?: Citation[];
};

export type UploadedFile = {
  name: string;
  size: number;
};

export type DomainScore = {
  domain: string;
  score: number;
  total_controls: number;
  passed: number;
  partial: number;
  failed: number;
  no_evidence: number;
};

export type Assessment = {
  id: string;
  vendorName: string;
  criticality: "Low" | "Medium" | "High";
  createdAt: string;
  status: "Draft" | "Running" | "Completed";
  score: number;
  riskLevel: "Low" | "Medium" | "High";
  controls: ControlResult[];
  notes: string;
  chatHistory: ChatMessage[];
  uploadedFiles: UploadedFile[];
  links: string[];
  domainScores?: DomainScore[];
  gapsSummary?: string;
  warning?: string;
  error?: string;
  frameworkId?: string;
  reviewQueue?: string[];
  riskProfile?: RiskProfile | null;
  inherentRisk?: { tier: string; points: number } | null;
  residualRisk?: string | null;
  evidenceFreshness?: EvidenceFreshness | null;
};

