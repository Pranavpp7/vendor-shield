"""
VendorShield Security Controls
Grounded in NIST SP 800-53 Revision 5
Source: https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final

Each control has:
- id: unique identifier
- nist_ref: the official NIST SP 800-53 Rev.5 control it maps to
- domain: which of the 4 assessment categories it belongs to
- title: short name
- description: what this control means in plain English
- search_query: what we ask the vector DB to find in vendor docs
- what_to_look_for: concepts and phrases the AI should find as evidence
- what_good_looks_like: what NIST actually requires (the standard)
- scoring_guide: how to score Pass / Partial / Fail / No Evidence
- weight: how much this control contributes to the domain score (all equal = 1)
"""

SECURITY_CONTROLS = [

    # -------------------------------------------------------------------------
    # DOMAIN 1: IDENTITY & ACCESS MANAGEMENT (5 controls)
    # NIST Family: IA - Identification and Authentication
    #              AC - Access Control
    # -------------------------------------------------------------------------

    {
        "id": "IAM-001",
        "nist_ref": "NIST SP 800-53 Rev.5 IA-2, IA-2(1), IA-2(2)",
        "domain": "Identity & Access Management",
        "title": "Multi-factor authentication enforced",
        "description": (
            "The vendor requires users to prove their identity using at least "
            "two different methods before gaining access to systems or data. "
            "A password alone is not sufficient."
        ),
        "search_query": (
            "multi-factor authentication MFA two-factor authentication 2FA "
            "secondary verification login security authenticator"
        ),
        "what_to_look_for": (
            "Any evidence that users must complete more than one verification "
            "step to log in. Look for: MFA, 2FA, two-factor authentication, "
            "multi-factor authentication, authenticator app, OTP, one-time "
            "password, hardware token, YubiKey, biometric verification, "
            "secondary verification, second factor, dual authentication, "
            "SMS verification code, push notification approval. "
            "Also look for whether it applies to ALL users or only admins."
        ),
        "what_good_looks_like": (
            "NIST IA-2(1) requires MFA for privileged accounts. "
            "NIST IA-2(2) requires MFA for non-privileged accounts. "
            "Best practice: MFA required for ALL users with no exceptions, "
            "using phishing-resistant methods (app-based or hardware token "
            "preferred over SMS). Policy should be enforced, not optional."
        ),
        "scoring_guide": {
            "pass": "MFA clearly required for all users, mechanism described",
            "partial": "MFA mentioned but only for admins, or described as optional, or mechanism unclear",
            "fail": "Document explicitly states password-only authentication",
            "no_evidence": "No mention of authentication beyond password anywhere in documents"
        },
        "weight": 1
    },

    {
        "id": "IAM-002",
        "nist_ref": "NIST SP 800-53 Rev.5 AC-2, AC-2(1)",
        "domain": "Identity & Access Management",
        "title": "Role-based access control implemented",
        "description": (
            "Users only have access to the systems and data they need for "
            "their specific job role. Someone in accounting cannot access "
            "engineering systems, for example."
        ),
        "search_query": (
            "role-based access control RBAC least privilege access management "
            "user permissions roles authorization"
        ),
        "what_to_look_for": (
            "Evidence that access is granted based on job roles and "
            "responsibilities. Look for: role-based access control, RBAC, "
            "least privilege, need-to-know basis, access roles, permission "
            "levels, user groups, access tiers, authorization matrix, "
            "role assignments, access provisioning process, job function "
            "based access, segregation of duties."
        ),
        "what_good_looks_like": (
            "NIST AC-2 requires organizations to manage accounts including "
            "defining roles, privileges, and access authorizations for each "
            "account type. NIST AC-6 (Least Privilege) requires granting "
            "only the minimum access necessary for each user's job function. "
            "Access should be reviewed regularly and revoked when no longer needed."
        ),
        "scoring_guide": {
            "pass": "RBAC or least privilege explicitly described with role definitions",
            "partial": "Access control mentioned but vague, no specific role structure described",
            "fail": "Evidence that users have unrestricted or overly broad access",
            "no_evidence": "No access control policy or user permission structure described"
        },
        "weight": 1
    },

    {
        "id": "IAM-003",
        "nist_ref": "NIST SP 800-53 Rev.5 AC-2(3), AC-6(5)",
        "domain": "Identity & Access Management",
        "title": "Privileged access management in place",
        "description": (
            "Administrator and superuser accounts are tightly controlled, "
            "monitored, and limited to only those who absolutely need them. "
            "These accounts have the most power and are the biggest security risk."
        ),
        "search_query": (
            "privileged access management PAM administrator accounts superuser "
            "admin access controls elevated privileges"
        ),
        "what_to_look_for": (
            "Evidence that high-privilege accounts are specially managed. "
            "Look for: privileged access management, PAM, administrator "
            "account controls, superuser access, root access restrictions, "
            "admin account monitoring, privileged session management, "
            "just-in-time access, elevated privilege controls, "
            "separation of admin duties, privileged identity management."
        ),
        "what_good_looks_like": (
            "NIST AC-6(5) requires restricting privileged accounts to "
            "authorized personnel only. NIST AC-2(3) requires disabling "
            "accounts after a defined period of inactivity. Best practice: "
            "Admin accounts should be separate from regular accounts, "
            "sessions logged, and access granted only when needed (just-in-time)."
        ),
        "scoring_guide": {
            "pass": "PAM program described with specific controls on admin accounts",
            "partial": "Admin accounts mentioned but limited controls described",
            "fail": "Evidence of shared or poorly controlled admin accounts",
            "no_evidence": "No mention of privileged account management"
        },
        "weight": 1
    },

    {
        "id": "IAM-004",
        "nist_ref": "NIST SP 800-53 Rev.5 AC-2(4), AC-2(7)",
        "domain": "Identity & Access Management",
        "title": "Regular access reviews conducted",
        "description": (
            "The vendor periodically reviews who has access to what, and "
            "removes access that is no longer needed. This prevents former "
            "employees or changed roles from retaining unnecessary access."
        ),
        "search_query": (
            "access review user access recertification account review "
            "periodic review access rights audit entitlement review"
        ),
        "what_to_look_for": (
            "Evidence that access rights are reviewed on a schedule. "
            "Look for: access review, access recertification, user access "
            "review, periodic access audit, entitlement review, access "
            "certification, quarterly review, annual review, access "
            "revocation process, offboarding procedures, account deprovisioning."
        ),
        "what_good_looks_like": (
            "NIST AC-2 requires reviewing accounts for compliance with "
            "account management requirements at a defined frequency. "
            "Best practice: formal access reviews at least quarterly for "
            "privileged accounts and annually for standard accounts, "
            "with documented evidence and timely remediation of findings."
        ),
        "scoring_guide": {
            "pass": "Access reviews described with defined frequency and process",
            "partial": "Reviews mentioned but frequency unclear or process informal",
            "fail": "Evidence that access is never reviewed or revoked",
            "no_evidence": "No mention of access reviews or account lifecycle management"
        },
        "weight": 1
    },

    {
        "id": "IAM-005",
        "nist_ref": "NIST SP 800-53 Rev.5 IA-5, IA-5(1)",
        "domain": "Identity & Access Management",
        "title": "Password policy meets security standards",
        "description": (
            "The vendor enforces strong password requirements including "
            "minimum length, complexity, and restrictions on reusing "
            "old passwords."
        ),
        "search_query": (
            "password policy password requirements minimum length complexity "
            "password expiration password reuse credentials"
        ),
        "what_to_look_for": (
            "Evidence of a documented and enforced password policy. "
            "Look for: password policy, minimum password length, password "
            "complexity requirements, uppercase lowercase numbers special "
            "characters, password expiration, password history, no password "
            "reuse, account lockout after failed attempts, password strength, "
            "credential management policy."
        ),
        "what_good_looks_like": (
            "NIST IA-5(1) requires passwords meet minimum complexity and "
            "length requirements, prohibit reuse of a defined number of "
            "previous passwords, and enforce a minimum/maximum lifetime. "
            "Current NIST SP 800-63B guidance recommends minimum 8 characters "
            "(12+ preferred), no mandatory periodic changes unless compromised, "
            "and checking against known breached password lists."
        ),
        "scoring_guide": {
            "pass": "Password policy documented with specific requirements enforced",
            "partial": "Password policy exists but missing key elements like length or lockout",
            "fail": "Weak or no password requirements evidenced",
            "no_evidence": "No password policy mentioned anywhere in documents"
        },
        "weight": 1
    },

    # -------------------------------------------------------------------------
    # DOMAIN 2: DATA PROTECTION (5 controls)
    # NIST Family: SC - System and Communications Protection
    #              MP - Media Protection
    # -------------------------------------------------------------------------

    {
        "id": "DP-001",
        "nist_ref": "NIST SP 800-53 Rev.5 SC-28, SC-28(1)",
        "domain": "Data Protection",
        "title": "Data encrypted at rest",
        "description": (
            "All data stored by the vendor — in databases, files, backups — "
            "is encrypted. Even if someone physically steals a hard drive, "
            "they cannot read the data without the encryption key."
        ),
        "search_query": (
            "encryption at rest data encryption stored data AES encrypted "
            "database encryption storage encryption encrypted files"
        ),
        "what_to_look_for": (
            "Evidence that stored data is encrypted. Look for: encryption "
            "at rest, data at rest encryption, AES-256, AES-128, encrypted "
            "storage, encrypted database, disk encryption, full disk "
            "encryption, encrypted backups, transparent data encryption, "
            "TDE, BitLocker, FileVault, cryptographic protection of stored data."
        ),
        "what_good_looks_like": (
            "NIST SC-28 requires protection of information at rest. "
            "SC-28(1) specifically requires cryptographic mechanisms. "
            "Best practice: AES-256 encryption for all data at rest including "
            "databases, file systems, and backups. Encryption keys should be "
            "managed separately from the encrypted data."
        ),
        "scoring_guide": {
            "pass": "Encryption at rest confirmed with algorithm specified (e.g. AES-256)",
            "partial": "Encryption mentioned but algorithm, scope, or key management unclear",
            "fail": "Data explicitly stored without encryption",
            "no_evidence": "No mention of data storage security or encryption at rest"
        },
        "weight": 1
    },

    {
        "id": "DP-002",
        "nist_ref": "NIST SP 800-53 Rev.5 SC-8, SC-8(1)",
        "domain": "Data Protection",
        "title": "Data encrypted in transit",
        "description": (
            "All data moving between systems, applications, or users is "
            "encrypted so it cannot be intercepted and read by anyone "
            "in the middle of the transmission."
        ),
        "search_query": (
            "encryption in transit TLS SSL HTTPS data transmission "
            "encrypted communications transport security"
        ),
        "what_to_look_for": (
            "Evidence that data is encrypted when moving between systems. "
            "Look for: TLS, SSL, HTTPS, encryption in transit, encrypted "
            "communications, secure transmission, transport layer security, "
            "TLS 1.2, TLS 1.3, encrypted API calls, secure channels, "
            "end-to-end encryption, mutual TLS, mTLS."
        ),
        "what_good_looks_like": (
            "NIST SC-8 requires protection of transmitted information. "
            "SC-8(1) requires cryptographic mechanisms. Best practice: "
            "TLS 1.2 minimum (TLS 1.3 preferred) for all data in transit, "
            "including internal service-to-service communication. "
            "Older protocols (SSL, TLS 1.0, TLS 1.1) should be disabled."
        ),
        "scoring_guide": {
            "pass": "TLS or HTTPS confirmed for all data in transit with version specified",
            "partial": "Encrypted transmission mentioned but version unclear or partial coverage",
            "fail": "Evidence of unencrypted data transmission",
            "no_evidence": "No mention of transmission security or encryption in transit"
        },
        "weight": 1
    },

    {
        "id": "DP-003",
        "nist_ref": "NIST SP 800-53 Rev.5 RA-2, MP-3",
        "domain": "Data Protection",
        "title": "Data classification policy implemented",
        "description": (
            "The vendor categorizes data by sensitivity level (e.g. public, "
            "internal, confidential, restricted) and applies appropriate "
            "security controls to each category."
        ),
        "search_query": (
            "data classification data categorization sensitive data "
            "confidential restricted public information classification"
        ),
        "what_to_look_for": (
            "Evidence of a formal data classification scheme. Look for: "
            "data classification, data categorization, sensitivity levels, "
            "confidential data, restricted data, public data, internal data, "
            "data labeling, information classification policy, data handling "
            "procedures by classification, PII classification, sensitive "
            "information handling."
        ),
        "what_good_looks_like": (
            "NIST RA-2 requires categorizing information and systems based "
            "on potential impact. MP-3 requires marking media with security "
            "classifications. Best practice: defined classification tiers "
            "(typically 3-4 levels), clear criteria for each, mandatory "
            "labeling of data assets, and different handling procedures "
            "for each classification level."
        ),
        "scoring_guide": {
            "pass": "Classification scheme defined with tiers and handling procedures",
            "partial": "Classification mentioned but tiers vague or procedures not described",
            "fail": "Evidence of treating all data equally regardless of sensitivity",
            "no_evidence": "No data classification policy mentioned"
        },
        "weight": 1
    },

    {
        "id": "DP-004",
        "nist_ref": "NIST SP 800-53 Rev.5 SI-12, MP-6",
        "domain": "Data Protection",
        "title": "Data retention policy defined",
        "description": (
            "The vendor has clear rules about how long different types of "
            "data are kept, and data is deleted or archived after that "
            "period. This limits exposure if a breach occurs."
        ),
        "search_query": (
            "data retention policy data lifecycle data deletion data "
            "archiving retention period records management"
        ),
        "what_to_look_for": (
            "Evidence of defined data retention timeframes. Look for: "
            "data retention policy, retention period, data lifecycle "
            "management, data deletion, data archiving, records retention, "
            "how long data is kept, when data is deleted, data purging, "
            "retention schedule, legal hold, data expiration."
        ),
        "what_good_looks_like": (
            "NIST SI-12 requires managing and retaining information within "
            "the system according to applicable laws and policies. "
            "Best practice: documented retention periods per data type, "
            "automated deletion when retention expires, legal hold process "
            "for data subject to investigation, and retention aligned with "
            "regulatory requirements (GDPR, HIPAA, SOX etc.)."
        ),
        "scoring_guide": {
            "pass": "Retention periods defined per data type with deletion process described",
            "partial": "Retention policy exists but periods vague or process unclear",
            "fail": "Evidence of indefinite data retention with no deletion process",
            "no_evidence": "No mention of data retention or deletion policies"
        },
        "weight": 1
    },

    {
        "id": "DP-005",
        "nist_ref": "NIST SP 800-53 Rev.5 MP-6, MP-6(1)",
        "domain": "Data Protection",
        "title": "Secure data disposal procedures",
        "description": (
            "When data or hardware is no longer needed, the vendor has "
            "formal procedures to destroy it securely so it cannot be "
            "recovered by unauthorized parties."
        ),
        "search_query": (
            "data disposal secure deletion data destruction media sanitization "
            "data wiping hardware disposal degaussing shredding"
        ),
        "what_to_look_for": (
            "Evidence of secure data and media disposal practices. "
            "Look for: secure disposal, data destruction, secure deletion, "
            "media sanitization, data wiping, degaussing, physical shredding, "
            "certificate of destruction, DoD wipe standards, NIST 800-88 "
            "media sanitization, hardware disposal policy, end-of-life "
            "data handling, cryptographic erasure."
        ),
        "what_good_looks_like": (
            "NIST MP-6 requires sanitizing media before disposal or reuse. "
            "MP-6(1) requires reviewing, approving, tracking, and verifying "
            "sanitization of media. Best practice: following NIST SP 800-88 "
            "Guidelines for Media Sanitization, maintaining certificates of "
            "destruction, and different methods per media type "
            "(overwrite for HDDs, degauss or physical destruction for tapes)."
        ),
        "scoring_guide": {
            "pass": "Secure disposal method described with verification process",
            "partial": "Disposal mentioned but method or verification not specified",
            "fail": "Evidence that media is discarded without sanitization",
            "no_evidence": "No mention of data disposal or media sanitization"
        },
        "weight": 1
    },

    # -------------------------------------------------------------------------
    # DOMAIN 3: SECURITY OPERATIONS (5 controls)
    # NIST Family: RA - Risk Assessment
    #              SI - System and Information Integrity
    #              IR - Incident Response
    #              CM - Configuration Management
    # -------------------------------------------------------------------------

    {
        "id": "SO-001",
        "nist_ref": "NIST SP 800-53 Rev.5 RA-5, RA-5(2)",
        "domain": "Security Operations",
        "title": "Vulnerability management program",
        "description": (
            "The vendor regularly scans their systems for security weaknesses "
            "and has a process to track and fix those weaknesses in a "
            "timely manner."
        ),
        "search_query": (
            "vulnerability management vulnerability scanning security scanning "
            "vulnerability assessment CVE vulnerability remediation"
        ),
        "what_to_look_for": (
            "Evidence of an active vulnerability management program. "
            "Look for: vulnerability management, vulnerability scanning, "
            "security scanning, vulnerability assessment, CVE tracking, "
            "vulnerability remediation, security testing, automated scanning, "
            "CVSS scoring, vulnerability prioritization, patch prioritization "
            "based on severity, vulnerability disclosure program, bug bounty."
        ),
        "what_good_looks_like": (
            "NIST RA-5 requires scanning for vulnerabilities in systems "
            "and applications at defined frequencies. RA-5(2) requires "
            "updating vulnerability scan information before new scans or "
            "when new vulnerabilities are identified. Best practice: "
            "automated scanning at least monthly, critical vulnerabilities "
            "remediated within 30 days, high within 60 days, tracked to closure."
        ),
        "scoring_guide": {
            "pass": "Vulnerability program described with scanning frequency and SLAs",
            "partial": "Scanning mentioned but frequency or remediation process unclear",
            "fail": "Evidence of known vulnerabilities left unaddressed",
            "no_evidence": "No mention of vulnerability scanning or management"
        },
        "weight": 1
    },

    {
        "id": "SO-002",
        "nist_ref": "NIST SP 800-53 Rev.5 SI-2, SI-2(2)",
        "domain": "Security Operations",
        "title": "Patch management process",
        "description": (
            "The vendor applies security patches and software updates in "
            "a timely manner to fix known security vulnerabilities before "
            "attackers can exploit them."
        ),
        "search_query": (
            "patch management software updates security patches patching "
            "update cycle patch deployment OS updates"
        ),
        "what_to_look_for": (
            "Evidence of a formal patching process. Look for: patch "
            "management, security patches, software updates, patch cycle, "
            "patching frequency, patch deployment, emergency patches, "
            "critical patch timeline, patch testing, OS updates, firmware "
            "updates, patch SLA, patch compliance tracking."
        ),
        "what_good_looks_like": (
            "NIST SI-2 requires identifying, reporting, and correcting "
            "information system flaws. SI-2(2) requires automated patch "
            "management. Best practice: critical patches applied within "
            "72 hours, high severity within 30 days, patch testing before "
            "production deployment, 99%+ patch compliance tracked, "
            "emergency patching process for zero-days."
        ),
        "scoring_guide": {
            "pass": "Patch process defined with timeframes per severity level",
            "partial": "Patching mentioned but timelines or scope unclear",
            "fail": "Evidence of delayed or absent patching",
            "no_evidence": "No mention of patch management or software updates"
        },
        "weight": 1
    },

    {
        "id": "SO-003",
        "nist_ref": "NIST SP 800-53 Rev.5 CA-8, CA-8(1)",
        "domain": "Security Operations",
        "title": "Regular penetration testing performed",
        "description": (
            "The vendor hires independent security experts to actively try "
            "to break into their systems — simulating a real attacker — "
            "to find vulnerabilities before real attackers do."
        ),
        "search_query": (
            "penetration testing pen test ethical hacking security testing "
            "red team third-party security assessment"
        ),
        "what_to_look_for": (
            "Evidence of penetration testing by qualified parties. "
            "Look for: penetration testing, pen testing, pen test, "
            "ethical hacking, red team, red team exercise, security "
            "assessment, third-party security testing, external security "
            "audit, offensive security testing, application security testing, "
            "annual penetration test, independent assessment."
        ),
        "what_good_looks_like": (
            "NIST CA-8 requires penetration testing on systems and "
            "system components. CA-8(1) requires independent penetration "
            "testing agents. Best practice: annual penetration tests at "
            "minimum by independent qualified third parties, scope covering "
            "both network and application layers, findings tracked to "
            "remediation, results reviewed by leadership."
        ),
        "scoring_guide": {
            "pass": "Pen testing confirmed with frequency and independent party specified",
            "partial": "Security testing mentioned but frequency, scope, or independence unclear",
            "fail": "Evidence that no external security testing is conducted",
            "no_evidence": "No mention of penetration testing or security assessments"
        },
        "weight": 1
    },

    {
        "id": "SO-004",
        "nist_ref": "NIST SP 800-53 Rev.5 IR-1, IR-4, IR-8",
        "domain": "Security Operations",
        "title": "Incident response plan in place",
        "description": (
            "The vendor has a documented, tested plan for what to do when "
            "a security incident occurs — including who does what, how "
            "customers are notified, and how systems are recovered."
        ),
        "search_query": (
            "incident response plan security incident breach notification "
            "incident management IR plan incident handling"
        ),
        "what_to_look_for": (
            "Evidence of a formal incident response capability. Look for: "
            "incident response plan, incident response policy, IR plan, "
            "security incident, breach response, incident handling, "
            "incident management, breach notification, incident response "
            "team, CIRT, CSIRT, SOC response, incident escalation, "
            "incident playbooks, tabletop exercise, incident SLA."
        ),
        "what_good_looks_like": (
            "NIST IR-1 requires an incident response policy and procedures. "
            "NIST IR-4 requires incident handling capabilities covering "
            "preparation, detection, containment, eradication, and recovery. "
            "IR-8 requires an incident response plan. Best practice: "
            "documented plan tested at least annually, defined roles and "
            "responsibilities, customer notification within 72 hours of "
            "confirmed breach, post-incident reviews."
        ),
        "scoring_guide": {
            "pass": "IR plan documented with roles, notification timelines, and testing",
            "partial": "IR plan exists but testing, timelines, or scope incomplete",
            "fail": "Evidence of no formal incident response capability",
            "no_evidence": "No mention of incident response or breach handling"
        },
        "weight": 1
    },

    {
        "id": "SO-005",
        "nist_ref": "NIST SP 800-53 Rev.5 SI-4, SI-4(2)",
        "domain": "Security Operations",
        "title": "Security monitoring and alerting",
        "description": (
            "The vendor continuously monitors their systems for suspicious "
            "activity and has automated alerts that notify security staff "
            "when something unusual is detected."
        ),
        "search_query": (
            "security monitoring alerting threat detection intrusion detection "
            "SOC security operations center real-time monitoring"
        ),
        "what_to_look_for": (
            "Evidence of active security monitoring. Look for: security "
            "monitoring, threat detection, intrusion detection, IDS, IPS, "
            "security operations center, SOC, real-time alerting, anomaly "
            "detection, behavioral analytics, UEBA, threat intelligence, "
            "security event monitoring, 24/7 monitoring, continuous monitoring."
        ),
        "what_good_looks_like": (
            "NIST SI-4 requires monitoring systems to detect attacks and "
            "indicators of potential attacks. SI-4(2) requires automated "
            "tools to support near real-time analysis of events. "
            "Best practice: 24/7 SOC coverage, automated alerting with "
            "defined response times, integration with threat intelligence "
            "feeds, and regular tuning to reduce false positives."
        ),
        "scoring_guide": {
            "pass": "Continuous monitoring with automated alerting and SOC coverage described",
            "partial": "Monitoring mentioned but coverage, automation, or response unclear",
            "fail": "Evidence of reactive rather than proactive security monitoring",
            "no_evidence": "No mention of security monitoring or threat detection"
        },
        "weight": 1
    },

    # -------------------------------------------------------------------------
    # DOMAIN 4: LOGGING & MONITORING (5 controls)
    # NIST Family: AU - Audit and Accountability
    # -------------------------------------------------------------------------

    {
        "id": "LM-001",
        "nist_ref": "NIST SP 800-53 Rev.5 AU-2, AU-12",
        "domain": "Logging & Monitoring",
        "title": "Centralized logging implemented",
        "description": (
            "All systems send their logs to one central location, making "
            "it possible to search across all logs in one place during "
            "an investigation or audit."
        ),
        "search_query": (
            "centralized logging log management SIEM log aggregation "
            "log collection centralized log repository"
        ),
        "what_to_look_for": (
            "Evidence of centralized log collection. Look for: centralized "
            "logging, log management, SIEM, log aggregation, log collector, "
            "central log repository, log forwarding, syslog, log pipeline, "
            "Splunk, ELK stack, Datadog, Sumo Logic, log consolidation, "
            "unified logging platform."
        ),
        "what_good_looks_like": (
            "NIST AU-2 requires defining what events to log. AU-12 requires "
            "systems to generate audit records. Best practice: all systems "
            "forward logs to a centralized SIEM or log management platform, "
            "logs are indexed and searchable, access to logs is restricted "
            "and monitored, and logs are protected from tampering."
        ),
        "scoring_guide": {
            "pass": "Centralized logging platform described with systems covered",
            "partial": "Logging exists but not centralized, or coverage incomplete",
            "fail": "Evidence of siloed or absent logging",
            "no_evidence": "No mention of logging infrastructure or log management"
        },
        "weight": 1
    },

    {
        "id": "LM-002",
        "nist_ref": "NIST SP 800-53 Rev.5 AU-6, IR-5",
        "domain": "Logging & Monitoring",
        "title": "Real-time alerting configured",
        "description": (
            "The logging system is configured to automatically trigger "
            "alerts when suspicious patterns are detected, so security "
            "teams can respond quickly."
        ),
        "search_query": (
            "real-time alerting security alerts automated alerts "
            "log-based alerts threshold alerts alert rules monitoring alerts"
        ),
        "what_to_look_for": (
            "Evidence of automated alerting from logs. Look for: real-time "
            "alerts, automated alerting, alert rules, threshold alerts, "
            "alert notifications, security alerts, log-based alerts, "
            "correlation rules, SIEM alerts, anomaly alerts, alert "
            "escalation, paging, on-call alerting, automated response."
        ),
        "what_good_looks_like": (
            "NIST AU-6 requires reviewing and analyzing audit records for "
            "indications of inappropriate activity. IR-5 requires tracking "
            "and documenting incidents. Best practice: automated alert rules "
            "for known attack patterns, alerts routed to on-call engineers "
            "24/7, defined response SLAs per alert severity, and regular "
            "review of alert rules to remove false positives."
        ),
        "scoring_guide": {
            "pass": "Real-time automated alerting described with escalation process",
            "partial": "Alerting mentioned but automation, coverage, or response unclear",
            "fail": "Evidence of manual-only log review with no automated alerts",
            "no_evidence": "No mention of alerting or automated log analysis"
        },
        "weight": 1
    },

    {
        "id": "LM-003",
        "nist_ref": "NIST SP 800-53 Rev.5 AU-3, AU-9",
        "domain": "Logging & Monitoring",
        "title": "Audit trail for all admin actions",
        "description": (
            "Every action taken by administrators — creating accounts, "
            "changing settings, accessing data — is logged with enough "
            "detail to reconstruct exactly what happened and who did it."
        ),
        "search_query": (
            "audit trail audit log admin actions administrative logging "
            "user activity logging audit records privileged actions"
        ),
        "what_to_look_for": (
            "Evidence that administrative and privileged actions are logged. "
            "Look for: audit trail, audit log, audit records, admin activity "
            "logging, privileged action logging, user activity logs, "
            "who did what when, access logging, change logging, immutable "
            "audit logs, tamper-evident logs, admin session recording."
        ),
        "what_good_looks_like": (
            "NIST AU-3 requires audit records to contain sufficient "
            "information to establish what, when, where, and who. "
            "AU-9 requires protecting audit information from unauthorized "
            "access, modification, and deletion. Best practice: all admin "
            "actions logged with user ID, timestamp, action taken, and "
            "resources affected. Logs should be immutable and separately "
            "protected from the systems they cover."
        ),
        "scoring_guide": {
            "pass": "Admin audit trail described as comprehensive, immutable, and protected",
            "partial": "Some admin logging described but completeness or protection unclear",
            "fail": "Evidence that admin actions are not logged",
            "no_evidence": "No mention of audit trails or administrative logging"
        },
        "weight": 1
    },

    {
        "id": "LM-004",
        "nist_ref": "NIST SP 800-53 Rev.5 AU-11",
        "domain": "Logging & Monitoring",
        "title": "Log retention policy meets minimum standards",
        "description": (
            "Logs are kept for a minimum period (typically 12 months) so "
            "that investigations into past incidents can access the full "
            "history of events."
        ),
        "search_query": (
            "log retention policy log storage duration audit log retention "
            "12 months log archive log history how long logs kept"
        ),
        "what_to_look_for": (
            "Evidence of a defined log retention timeframe. Look for: "
            "log retention, log retention policy, audit log retention, "
            "how long logs are kept, log storage duration, 12 months, "
            "one year, 90 days, log archiving, log lifecycle, "
            "compliance-driven retention, log purging schedule."
        ),
        "what_good_looks_like": (
            "NIST AU-11 requires retaining audit records for a defined "
            "period to provide support for after-the-fact investigations. "
            "Best practice: minimum 12 months online (searchable) retention, "
            "with 24+ months in cold archive. Many regulations (PCI DSS, "
            "HIPAA, SOX) mandate specific minimums. Retention period should "
            "be documented and enforced automatically."
        ),
        "scoring_guide": {
            "pass": "Retention period defined at 12+ months with archiving described",
            "partial": "Retention mentioned but period shorter than 12 months or unspecified",
            "fail": "Evidence of very short retention or logs deleted too quickly",
            "no_evidence": "No mention of log retention policy or duration"
        },
        "weight": 1
    },

    {
        "id": "LM-005",
        "nist_ref": "NIST SP 800-53 Rev.5 SI-4(2), AU-6(1)",
        "domain": "Logging & Monitoring",
        "title": "SIEM integration available",
        "description": (
            "The vendor uses a Security Information and Event Management "
            "system (SIEM) that correlates logs from multiple sources to "
            "detect complex attack patterns that no single log would reveal."
        ),
        "search_query": (
            "SIEM security information event management log correlation "
            "Splunk QRadar Microsoft Sentinel threat intelligence integration"
        ),
        "what_to_look_for": (
            "Evidence of SIEM use or equivalent correlation capability. "
            "Look for: SIEM, security information and event management, "
            "log correlation, Splunk, IBM QRadar, Microsoft Sentinel, "
            "Elastic SIEM, ArcSight, LogRhythm, threat intelligence "
            "integration, correlation rules, event correlation, "
            "cross-system log analysis, security analytics platform."
        ),
        "what_good_looks_like": (
            "NIST SI-4(2) requires automated tools for near real-time "
            "event analysis. AU-6(1) requires integrating audit review, "
            "analysis, and reporting with threat and vulnerability information. "
            "Best practice: enterprise SIEM with correlation rules covering "
            "all critical systems, updated threat intelligence feeds, "
            "integration with ticketing for alert management."
        ),
        "scoring_guide": {
            "pass": "SIEM platform named and described with correlation capability",
            "partial": "Log aggregation described but correlation or SIEM unclear",
            "fail": "Evidence of manual-only log analysis without automated correlation",
            "no_evidence": "No mention of SIEM or log correlation capabilities"
        },
        "weight": 1
    },

]

# -------------------------------------------------------------------------
# Helper functions your application will use
# -------------------------------------------------------------------------

def get_all_controls():
    """Return all 20 controls."""
    return SECURITY_CONTROLS

def get_controls_by_domain(domain: str):
    """Return controls filtered by domain name."""
    return [c for c in SECURITY_CONTROLS if c["domain"] == domain]

def get_domains():
    """Return the list of unique domains."""
    seen = []
    for c in SECURITY_CONTROLS:
        if c["domain"] not in seen:
            seen.append(c["domain"])
    return seen

def get_scoring_prompt(control: dict, retrieved_chunks: list[str]) -> str:
    """
    Build the prompt we send to the LLM for scoring a control.
    This is the instruction that tells the LLM exactly how to judge.

    retrieved_chunks: list of paragraphs found by the vector search
    """
    chunks_text = "\n\n---\n\n".join(
        [f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(retrieved_chunks)]
    )

    return f"""You are a security auditor conducting a vendor risk assessment.

CONTROL BEING ASSESSED:
Control ID: {control['id']}
NIST Reference: {control['nist_ref']}
Control Title: {control['title']}
Control Description: {control['description']}

WHAT GOOD LOOKS LIKE (the standard):
{control['what_good_looks_like']}

RETRIEVED EVIDENCE FROM VENDOR DOCUMENTS:
{chunks_text}

SCORING INSTRUCTIONS:
Based ONLY on the evidence above from the vendor's own documents, score this control.
Do NOT use any knowledge outside of these documents.

Score definitions:
- PASS: Clear, specific evidence that the vendor meets this control
- PARTIAL: Some evidence exists but it is vague, incomplete, or only partially meets the standard
- FAIL: The documents contain evidence that the vendor does NOT meet this control
- NO_EVIDENCE: The documents contain no relevant information about this control

Respond in this exact JSON format:
{{
  "control_id": "{control['id']}",
  "score": "PASS|PARTIAL|FAIL|NO_EVIDENCE",
  "confidence": "HIGH|MEDIUM|LOW",
  "evidence_quote": "exact quote from the vendor documents that supports your score, or null if NO_EVIDENCE",
  "evidence_chunk": 1,
  "reasoning": "1-2 sentence explanation of your scoring decision",
  "gap": "what is missing or needs improvement, or null if PASS"
}}
"""

# -------------------------------------------------------------------------
# Domain weights for overall score calculation
# -------------------------------------------------------------------------

DOMAIN_WEIGHTS = {
    "Identity & Access Management": 1.0,
    "Data Protection": 1.0,
    "Security Operations": 1.0,
    "Logging & Monitoring": 1.0,
}

# -------------------------------------------------------------------------
# Score calculation
# -------------------------------------------------------------------------

def calculate_scores(control_results: list[dict]) -> dict:
    """
    Given a list of scored controls, calculate domain and overall scores.

    control_results format:
    [{"control_id": "IAM-001", "score": "PASS", ...}, ...]

    Score values: PASS=1.0, PARTIAL=0.5, FAIL=0.0, NO_EVIDENCE=0.0
    """
    score_map = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0, "NO_EVIDENCE": 0.0}

    # Map results by control_id
    results_by_id = {r["control_id"]: r for r in control_results}

    domain_scores = {}
    all_scores = []

    for domain in get_domains():
        domain_controls = get_controls_by_domain(domain)
        domain_total = 0.0
        domain_count = len(domain_controls)

        for control in domain_controls:
            result = results_by_id.get(control["id"])
            if result:
                score_val = score_map.get(result["score"], 0.0)
                domain_total += score_val
                all_scores.append(score_val)
            else:
                all_scores.append(0.0)

        domain_pct = round((domain_total / domain_count) * 100) if domain_count > 0 else 0
        domain_scores[domain] = domain_pct

    overall = round(sum(all_scores) / len(all_scores) * 100) if all_scores else 0

    if overall >= 70:
        risk_level = "Low"
    elif overall >= 40:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return {
        "overall_score": overall,
        "risk_level": risk_level,
        "domain_scores": domain_scores,
    }
