export type ControlResult = {
  id: string;
  category: string;
  name: string;
  passed: boolean;
  comment: string;
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
  status: "Running" | "Completed";
  score: number;
  riskLevel: "Low" | "Medium" | "High";
  controls: ControlResult[];
  notes: string;
  chatHistory: ChatMessage[];
  uploadedFiles: UploadedFile[];
  links: string[];
};
