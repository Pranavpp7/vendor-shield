export type ControlStatus = "passed" | "failed" | "needs_info" | "partial";

export type Citation = {
  document: string;
  page?: number;
  excerpt: string;
  similarity?: number;
};

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
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
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
};

