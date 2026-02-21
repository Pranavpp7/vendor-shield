export const checklistSchema = [
  {
    category: "Identity & Access Management",
    controls: [
      { id: "iam-1", name: "MFA enforced for all users" },
      { id: "iam-2", name: "Role-based access control implemented" },
      { id: "iam-3", name: "Privileged access management in place" },
      { id: "iam-4", name: "Regular access reviews conducted" },
      { id: "iam-5", name: "SSO integration supported" },
    ],
  },
  {
    category: "Data Security",
    controls: [
      { id: "ds-1", name: "Data encrypted at rest (AES-256 or equivalent)" },
      { id: "ds-2", name: "Data encrypted in transit (TLS 1.2+)" },
      { id: "ds-3", name: "Data classification policy enforced" },
      { id: "ds-4", name: "DLP controls implemented" },
      { id: "ds-5", name: "Backup and recovery procedures documented" },
    ],
  },
  {
    category: "Compliance & Certifications",
    controls: [
      { id: "cc-1", name: "SOC 2 Type II certified" },
      { id: "cc-2", name: "ISO 27001 certified" },
      { id: "cc-3", name: "GDPR compliance documented" },
      { id: "cc-4", name: "Regular penetration testing performed" },
      { id: "cc-5", name: "Incident response plan in place" },
    ],
  },
  {
    category: "Logging & Monitoring",
    controls: [
      { id: "lm-1", name: "Centralized logging implemented" },
      { id: "lm-2", name: "Real-time alerting configured" },
      { id: "lm-3", name: "Audit trail for all admin actions" },
      { id: "lm-4", name: "Log retention policy (min 12 months)" },
      { id: "lm-5", name: "SIEM integration available" },
    ],
  },
];

export const allControlIds = checklistSchema.flatMap((g) =>
  g.controls.map((c) => c.id)
);
