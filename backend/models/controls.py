"""Internal controls repository — our policy checklist.

This is what makes VendorShield a policy-vs-vendor-doc assessment system,
not a generic AI scorer. Each control has evaluation guidance for the LLM.
"""

from models.schemas import ControlDefinition

INTERNAL_CONTROLS = [
    # ─── Identity & Access Management ───
    {
        "category": "Identity & Access Management",
        "controls": [
            ControlDefinition(
                id="iam-1",
                name="MFA enforced for all users",
                category="Identity & Access Management",
                description="Multi-factor authentication must be required for all user accounts, including admin and service accounts.",
                weight=1.0,
            ),
            ControlDefinition(
                id="iam-2",
                name="Role-based access control implemented",
                category="Identity & Access Management",
                description="RBAC with least-privilege principles. Users should only access resources necessary for their role.",
                weight=1.0,
            ),
            ControlDefinition(
                id="iam-3",
                name="Privileged access management in place",
                category="Identity & Access Management",
                description="PAM controls for admin/root accounts. Includes just-in-time access, session monitoring, and credential vaulting.",
                weight=1.0,
            ),
            ControlDefinition(
                id="iam-4",
                name="Regular access reviews conducted",
                category="Identity & Access Management",
                description="Periodic review of user access rights (at least quarterly). Includes offboarding procedures.",
                weight=0.8,
            ),
            ControlDefinition(
                id="iam-5",
                name="SSO integration supported",
                category="Identity & Access Management",
                description="Support for SAML 2.0 or OIDC based single sign-on integration with enterprise identity providers.",
                weight=0.8,
            ),
        ],
    },
    # ─── Data Security ───
    {
        "category": "Data Security",
        "controls": [
            ControlDefinition(
                id="ds-1",
                name="Data encrypted at rest (AES-256 or equivalent)",
                category="Data Security",
                description="All sensitive data must be encrypted at rest using AES-256 or equivalent algorithm. Includes database, file storage, and backups.",
                weight=1.0,
            ),
            ControlDefinition(
                id="ds-2",
                name="Data encrypted in transit (TLS 1.2+)",
                category="Data Security",
                description="All data in transit must use TLS 1.2 or higher. No plaintext protocols for sensitive data.",
                weight=1.0,
            ),
            ControlDefinition(
                id="ds-3",
                name="Data classification policy enforced",
                category="Data Security",
                description="Formal data classification scheme (e.g., Public, Internal, Confidential, Restricted) with handling procedures.",
                weight=0.8,
            ),
            ControlDefinition(
                id="ds-4",
                name="DLP controls implemented",
                category="Data Security",
                description="Data Loss Prevention controls to detect and prevent unauthorized data exfiltration.",
                weight=0.8,
            ),
            ControlDefinition(
                id="ds-5",
                name="Backup and recovery procedures documented",
                category="Data Security",
                description="Regular backups with documented recovery procedures. RTO and RPO defined and tested.",
                weight=0.8,
            ),
        ],
    },
    # ─── Compliance & Certifications ───
    {
        "category": "Compliance & Certifications",
        "controls": [
            ControlDefinition(
                id="cc-1",
                name="SOC 2 Type II certified",
                category="Compliance & Certifications",
                description="Current SOC 2 Type II report from an accredited auditor covering Security, Availability, and Confidentiality.",
                weight=1.0,
            ),
            ControlDefinition(
                id="cc-2",
                name="ISO 27001 certified",
                category="Compliance & Certifications",
                description="Current ISO 27001 certification demonstrating an established ISMS.",
                weight=1.0,
            ),
            ControlDefinition(
                id="cc-3",
                name="GDPR compliance documented",
                category="Compliance & Certifications",
                description="Documentation of GDPR compliance including DPA, data processing records, and privacy impact assessments.",
                weight=0.8,
            ),
            ControlDefinition(
                id="cc-4",
                name="Regular penetration testing performed",
                category="Compliance & Certifications",
                description="Annual or more frequent penetration testing by qualified third-party assessors. Remediation tracked.",
                weight=1.0,
            ),
            ControlDefinition(
                id="cc-5",
                name="Incident response plan in place",
                category="Compliance & Certifications",
                description="Documented incident response plan with defined roles, escalation paths, and communication procedures. Regularly tested.",
                weight=1.0,
            ),
        ],
    },
    # ─── Logging & Monitoring ───
    {
        "category": "Logging & Monitoring",
        "controls": [
            ControlDefinition(
                id="lm-1",
                name="Centralized logging implemented",
                category="Logging & Monitoring",
                description="All security-relevant events are collected in a centralized logging system.",
                weight=1.0,
            ),
            ControlDefinition(
                id="lm-2",
                name="Real-time alerting configured",
                category="Logging & Monitoring",
                description="Automated alerts for security events including unauthorized access, anomalies, and threshold breaches.",
                weight=0.8,
            ),
            ControlDefinition(
                id="lm-3",
                name="Audit trail for all admin actions",
                category="Logging & Monitoring",
                description="Complete audit trail of all administrative and privileged actions. Tamper-resistant logs.",
                weight=1.0,
            ),
            ControlDefinition(
                id="lm-4",
                name="Log retention policy (min 12 months)",
                category="Logging & Monitoring",
                description="Security logs retained for at least 12 months, with at least 3 months immediately available.",
                weight=0.8,
            ),
            ControlDefinition(
                id="lm-5",
                name="SIEM integration available",
                category="Logging & Monitoring",
                description="Support for SIEM integration via standard protocols (syslog, API) for centralized security monitoring.",
                weight=0.6,
            ),
        ],
    },
]


def get_all_controls() -> list[ControlDefinition]:
    """Flatten all controls from all categories into a single list."""
    controls = []
    for category in INTERNAL_CONTROLS:
        controls.extend(category["controls"])
    return controls


def get_categories() -> list[str]:
    """Get list of all control category names."""
    return [cat["category"] for cat in INTERNAL_CONTROLS]


def get_controls_by_category(category: str) -> list[ControlDefinition]:
    """Get controls for a specific category."""
    for cat in INTERNAL_CONTROLS:
        if cat["category"] == category:
            return cat["controls"]
    return []
