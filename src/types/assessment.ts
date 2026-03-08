export type ControlStatus = "passed" | "failed" | "needs_info";

export type ControlResult = {
  id: string;
  category: string;
  name: string;
  passed: boolean;
  status: ControlStatus;
  comment: string;
  aiExplanation?: string;
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
};
