// Source of truth: backend/models/controls.py
// IDs, domain names, and titles must match the backend exactly so the
// frontend can correlate API responses (ControlResult.control_id) to
// the static checklist rows rendered before the assessment runs.

export const checklistSchema = [
  {
    category: "Identity & Access Management",
    controls: [
      { id: "IAM-001", name: "Multi-factor authentication enforced" },
      { id: "IAM-002", name: "Role-based access control implemented" },
      { id: "IAM-003", name: "Privileged access management in place" },
      { id: "IAM-004", name: "Regular access reviews conducted" },
      { id: "IAM-005", name: "Password policy meets security standards" },
    ],
  },
  {
    category: "Data Protection",
    controls: [
      { id: "DP-001", name: "Data encrypted at rest" },
      { id: "DP-002", name: "Data encrypted in transit" },
      { id: "DP-003", name: "Data classification policy implemented" },
      { id: "DP-004", name: "Data retention policy defined" },
      { id: "DP-005", name: "Secure data disposal procedures" },
    ],
  },
  {
    category: "Security Operations",
    controls: [
      { id: "SO-001", name: "Vulnerability management program" },
      { id: "SO-002", name: "Patch management process" },
      { id: "SO-003", name: "Regular penetration testing performed" },
      { id: "SO-004", name: "Incident response plan in place" },
      { id: "SO-005", name: "Security monitoring and alerting" },
    ],
  },
  {
    category: "Logging & Monitoring",
    controls: [
      { id: "LM-001", name: "Centralized logging implemented" },
      { id: "LM-002", name: "Real-time alerting configured" },
      { id: "LM-003", name: "Audit trail for all admin actions" },
      { id: "LM-004", name: "Log retention policy meets minimum standards" },
      { id: "LM-005", name: "SIEM integration available" },
    ],
  },
];

export const allControlIds = checklistSchema.flatMap((g) =>
  g.controls.map((c) => c.id)
);
