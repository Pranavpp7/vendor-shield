"""
Layer 3: Email & PDF Report Service.

RESPONSIBILITY:
    Generates a professional PDF risk assessment report entirely in memory
    (BytesIO — never touches disk) using ReportLab, and sends it as an
    email attachment via the Resend SDK.

    Two public functions:
    - generate_pdf_report(assessment) -> bytes
    - send_report_email(to_email, assessment) -> dict

IMPORTS FROM: config.py (for resend_api_key)
IMPORTED BY:  routers/email.py, mcp/server.py
"""

import base64
import logging
from io import BytesIO
from datetime import datetime

import resend
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from config import get_settings
from models.controls import effective_score as _effective

logger = logging.getLogger(__name__)

# ── Colour Constants ──────────────────────────────────────────────────────────
# Color objects for TableStyle; hex strings for Paragraph XML <font> tags.

GREEN        = colors.HexColor("#16a34a")
ORANGE       = colors.HexColor("#ea580c")
RED          = colors.HexColor("#dc2626")
DARK_BLUE    = colors.HexColor("#1e3a5f")
ACCENT_BLUE  = colors.HexColor("#2563eb")
LIGHT_GRAY   = colors.HexColor("#f8fafc")
FOOTER_GRAY  = colors.HexColor("#f1f5f9")
BORDER_GRAY  = colors.HexColor("#d1d5db")
DIVIDER_GRAY = colors.HexColor("#cbd5e1")
TEXT_GRAY    = colors.HexColor("#6b7280")
SLATE_GRAY   = colors.HexColor("#94a3b8")
WHITE        = colors.white
BLACK        = colors.black

GREEN_HEX  = "#16a34a"
ORANGE_HEX = "#ea580c"
RED_HEX    = "#dc2626"
BLUE_HEX   = "#2563eb"
SLATE_HEX  = "#94a3b8"

PAGE_W = 7.0 * inch   # 8.5" letter − 0.75" × 2 margins
EV_W   = PAGE_W       # evidence box uses full width

SCORE_COLOR_MAP = {
    "PASS":        (GREEN,      GREEN_HEX),
    "PARTIAL":     (ORANGE,     ORANGE_HEX),
    "FAIL":        (RED,        RED_HEX),
    "NO_EVIDENCE": (SLATE_GRAY, SLATE_HEX),
}

_NUMERIC_SCORE = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0, "NO_EVIDENCE": 0.0}

# Phrases that indicate an LLM/API error leaked into reasoning or evidence
_ERROR_MARKERS = (
    "LLM call failed",
    "LLM returned",
    "429",
    "rate limit",
    "unparseable",
    "Could not evaluate",
    "retry may help",
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _risk_label(score: float) -> str:
    if score >= 70:
        return "LOW"
    if score >= 40:
        return "MEDIUM"
    return "HIGH"


def _risk_color_obj(score: float) -> colors.Color:
    if score >= 70:
        return GREEN
    if score >= 40:
        return ORANGE
    return RED


def _risk_hex(score: float) -> str:
    if score >= 70:
        return GREEN_HEX
    if score >= 40:
        return ORANGE_HEX
    return RED_HEX


def _sanitize(text: str | None) -> str:
    """Replace LLM/API error strings with a user-friendly fallback.

    Applied to every reasoning and evidence_quote field before any text
    is passed to ReportLab — never lets raw API error messages into the PDF.
    """
    if not text:
        return ""
    if any(m in text for m in _ERROR_MARKERS):
        return (
            "Unable to evaluate — document did not contain sufficient "
            "evidence for this control."
        )
    return text


# ── PDF Generation ────────────────────────────────────────────────────────────


def generate_pdf_report(assessment: dict) -> bytes:
    """Generate a professional PDF risk report entirely in memory.

    Args:
        assessment: Full assessment dict from local JSON storage.

    Returns:
        Raw PDF bytes — ready to attach to an email or stream to a client.
        Never writes to disk.
    """
    buffer = BytesIO()

    # ── Extract & sanitize data ───────────────────────────────────────────
    vendor_name   = assessment.get("vendor_name", "Unknown Vendor")
    overall_score = assessment.get("overall_score", 0)
    domain_scores = assessment.get("domain_scores", {})
    raw_controls  = assessment.get("control_results", [])
    created_at    = assessment.get("created_at", "")
    risk          = _risk_label(overall_score)
    risk_col      = _risk_color_obj(overall_score)
    risk_hex      = _risk_hex(overall_score)

    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%B %d, %Y")
    except Exception:
        date_str = created_at[:10] if len(created_at) >= 10 else "N/A"

    # Fix 7: sanitize ALL control text fields before touching ReportLab
    controls = [
        {
            **c,
            "reasoning":      _sanitize(c.get("reasoning")),
            "evidence_quote": _sanitize(c.get("evidence_quote")),
        }
        for c in raw_controls
    ]

    # ── Canvas callback: page header on pages 2+ ──────────────────────────
    def later_pages(canvas, doc):
        canvas.saveState()
        pg_w, pg_h = letter
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(TEXT_GRAY)
        canvas.drawString(
            0.75 * inch, pg_h - 0.38 * inch,
            "VendorShield — Confidential",
        )
        canvas.drawRightString(
            pg_w - 0.75 * inch, pg_h - 0.38 * inch,
            vendor_name,
        )
        canvas.setStrokeColor(BORDER_GRAY)
        canvas.setLineWidth(0.5)
        canvas.line(
            0.75 * inch,      pg_h - 0.5 * inch,
            pg_w - 0.75 * inch, pg_h - 0.5 * inch,
        )
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(SLATE_GRAY)
        canvas.drawRightString(
            pg_w - 0.75 * inch, 0.35 * inch,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.65 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    elements: list = []

    # ── Paragraph styles ──────────────────────────────────────────────────

    brand_style = ParagraphStyle(
        "Brand",
        fontName="Helvetica-Bold", fontSize=24,
        textColor=WHITE, leading=30,
    )
    banner_sub_style = ParagraphStyle(
        "BannerSub",
        fontName="Helvetica", fontSize=12,
        textColor=colors.HexColor("#cdd5e0"), leading=16, spaceBefore=3,
    )
    banner_vendor_style = ParagraphStyle(
        "BannerVendor",
        fontName="Helvetica-Bold", fontSize=12,
        textColor=WHITE, alignment=TA_RIGHT, leading=16,
    )
    banner_date_style = ParagraphStyle(
        "BannerDate",
        fontName="Helvetica", fontSize=10,
        textColor=colors.HexColor("#cdd5e0"), alignment=TA_RIGHT,
        leading=14, spaceBefore=3,
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        fontName="Helvetica-Bold", fontSize=13,
        textColor=DARK_BLUE, spaceBefore=14, spaceAfter=6,
    )
    domain_header_style = ParagraphStyle(
        "DomainHeader",
        fontName="Helvetica-Bold", fontSize=11,
        textColor=ACCENT_BLUE, spaceBefore=14, spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica", fontSize=9,
        textColor=BLACK, leading=12,
    )
    small_style = ParagraphStyle(
        "Small",
        fontName="Helvetica", fontSize=8,
        textColor=colors.HexColor("#374151"), leading=11,
    )
    summary_style = ParagraphStyle(
        "Summary",
        fontName="Helvetica", fontSize=9.5,
        textColor=colors.HexColor("#374151"), leading=14,
        spaceBefore=4, spaceAfter=4,
    )
    footer_style = ParagraphStyle(
        "Footer",
        fontName="Helvetica", fontSize=8,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER, leading=12,
    )

    # ─────────────────────────────────────────────────────────────────────
    # 1. HEADER BANNER
    # ─────────────────────────────────────────────────────────────────────

    header_data = [
        [
            Paragraph("VendorShield", brand_style),
            Paragraph(vendor_name, banner_vendor_style),
        ],
        [
            Paragraph("Vendor Risk Assessment Report", banner_sub_style),
            Paragraph(date_str, banner_date_style),
        ],
    ]
    header_table = Table(header_data, colWidths=[4.5 * inch, 2.5 * inch])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), DARK_BLUE),
        ("TOPPADDING",    (0, 0), (-1,  0), 22),
        ("TOPPADDING",    (0, 1), (-1,  1), 4),
        ("BOTTOMPADDING", (0, 1), (-1,  1), 18),
        ("LEFTPADDING",   (0, 0), (-1, -1), 20),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 20),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(header_table)
    # Thin accent line immediately below the banner
    elements.append(
        HRFlowable(
            width="100%", thickness=2, color=ACCENT_BLUE,
            spaceBefore=0, spaceAfter=16,
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # 2. OVERALL SCORE CARD  (white + colored left border)
    # ─────────────────────────────────────────────────────────────────────

    score_slash_style = ParagraphStyle(
        "ScoreSlash", fontName="Helvetica-Bold",
        fontSize=72, leading=84, alignment=TA_CENTER,
    )
    risk_lbl_style = ParagraphStyle(
        "RiskLbl", fontName="Helvetica-Bold",
        fontSize=18, leading=26, alignment=TA_CENTER,
        textColor=risk_col,
    )
    nist_note_style = ParagraphStyle(
        "NistNote", fontName="Helvetica", fontSize=8,
        textColor=TEXT_GRAY, alignment=TA_CENTER, leading=12, spaceBefore=4,
    )

    score_card_data = [
        [Paragraph(
            f'<font face="Helvetica-Bold" size="72" color="{risk_hex}">'
            f'{overall_score:.0f}</font>'
            f'<font face="Helvetica" size="18" color="#9ca3af"> / 100</font>',
            score_slash_style,
        )],
        [Paragraph(f"{risk} RISK", risk_lbl_style)],
        [Paragraph("Based on 20 NIST SP 800-53 Rev.5 controls", nist_note_style)],
    ]
    score_card = Table(score_card_data, colWidths=[PAGE_W])
    score_card.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), WHITE),
        ("TOPPADDING",    (0, 0), (-1,  0), 20),
        ("TOPPADDING",    (0, 1), (-1,  1), 4),
        ("TOPPADDING",    (0, 2), (-1,  2), 6),
        ("BOTTOMPADDING", (0, 2), (-1,  2), 20),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        # 4 pt colored left border
        ("LINEBEFORE",    (0, 0), (0,  -1), 4, risk_col),
    ]))
    elements.append(score_card)
    elements.append(Spacer(1, 16))

    # ─────────────────────────────────────────────────────────────────────
    # 8. EXECUTIVE SUMMARY
    # ─────────────────────────────────────────────────────────────────────

    # Effective (override-aware) counts — analyst verdicts supersede the AI's
    pass_count    = sum(1 for c in controls if _effective(c) == "PASS")
    partial_count = sum(1 for c in controls if _effective(c) == "PARTIAL")
    fail_count    = sum(1 for c in controls if _effective(c) == "FAIL")
    no_ev_count   = sum(1 for c in controls if _effective(c) == "NO_EVIDENCE")
    override_count = sum(1 for c in controls if c.get("analyst_score"))
    weakest_domain = (
        min(domain_scores, key=lambda d: domain_scores[d])
        if domain_scores else "the identified gaps"
    )

    # Framework name (falls back gracefully for legacy records)
    framework_id = assessment.get("framework_id", "nist-800-53")
    try:
        from models.controls import get_framework
        framework_name = get_framework(framework_id).get("name", framework_id)
    except Exception:
        framework_name = "NIST SP 800-53 Rev.5"

    verified_count = len(controls) - no_ev_count
    coverage_pct = round(verified_count / len(controls) * 100) if controls else 0
    summary_text = (
        f"VendorShield evaluated <b>{vendor_name}</b> against the "
        f"<b>{len(controls)}</b> security controls of <b>{framework_name}</b> "
        f"across {len(domain_scores) or 4} domains. "
        f"Of the <b>{verified_count}</b> controls verifiable from the provided "
        f"documents (<b>{coverage_pct}%</b> evidence coverage), "
        f"<b>{pass_count}</b> were fully satisfied, <b>{partial_count}</b> "
        f"partially satisfied, and <b>{fail_count}</b> found deficient. "
        f"<b>{no_ev_count}</b> controls could not be verified; unverified "
        f"controls count as unaccepted risk in the overall score (they are "
        f"not confirmed deficiencies — see the follow-up questions for the "
        f"evidence to request). "
        f"Focus is recommended on <b>{weakest_domain}</b>."
    )
    if override_count:
        summary_text += (
            f" <b>{override_count}</b> control verdict"
            f"{'s were' if override_count != 1 else ' was'} reviewed and adjusted "
            f"by an analyst; adjusted scores are used throughout this report."
        )

    # Inherent & residual risk, when an intake profile exists
    profile = assessment.get("risk_profile")
    if profile:
        try:
            from services.aggregation import compute_inherent_risk, compute_residual_risk
            inherent = compute_inherent_risk(profile)
            residual = compute_residual_risk(inherent["tier"], _risk_label(overall_score).capitalize())
            summary_text += (
                f" The vendor relationship carries <b>{inherent['tier']}</b> inherent "
                f"risk; combined with the assessed posture, the residual risk is "
                f"<b>{residual}</b>."
            )
        except Exception:
            pass

    elements.append(Paragraph("Executive Summary", section_title_style))
    elements.append(Paragraph(summary_text, summary_style))
    elements.append(Spacer(1, 14))

    # ─────────────────────────────────────────────────────────────────────
    # 3. DOMAIN SCORES TABLE
    # ─────────────────────────────────────────────────────────────────────

    elements.append(Paragraph("Domain Scores", section_title_style))

    domain_rows = [[
        Paragraph("<b>Domain</b>", body_style),
        Paragraph("<b>Score</b>", body_style),
        Paragraph("<b>Risk Level</b>", body_style),
    ]]
    for d_name, d_score in domain_scores.items():
        d_risk = _risk_label(d_score)
        d_hex  = _risk_hex(d_score)
        domain_rows.append([
            Paragraph(d_name, body_style),
            Paragraph(f"{d_score:.0f} / 100", body_style),
            Paragraph(f'<b><font color="{d_hex}">{d_risk}</font></b>', body_style),
        ])

    domain_table = Table(
        domain_rows,
        colWidths=[4.0 * inch, 1.3 * inch, 1.7 * inch],
    )
    domain_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), DARK_BLUE),
        ("TEXTCOLOR",     (0, 0), (-1,  0), WHITE),
        ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID",          (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    elements.append(domain_table)
    elements.append(Spacer(1, 18))

    # ─────────────────────────────────────────────────────────────────────
    # 4. CONTROL BREAKDOWN BY DOMAIN
    # ─────────────────────────────────────────────────────────────────────

    elements.append(Paragraph("Control Breakdown", section_title_style))

    # Group controls by domain
    domains_grouped: dict[str, list] = {}
    for ctrl in controls:
        domains_grouped.setdefault(ctrl.get("domain", "Other"), []).append(ctrl)

    for domain_name, ctrls in domains_grouped.items():
        # Domain section header: blue bold text + blue underline
        elements.append(Paragraph(domain_name, domain_header_style))
        elements.append(
            HRFlowable(
                width="100%", thickness=1, color=ACCENT_BLUE,
                spaceBefore=0, spaceAfter=6,
            )
        )

        # Control table (no duplicate control-ID standalone headers — fix 9)
        ctrl_header = [
            Paragraph("<b>ID</b>", body_style),
            Paragraph("<b>Control Title</b>", body_style),
            Paragraph("<b>Result</b>", body_style),
            Paragraph("<b>Score</b>", body_style),
        ]
        ctrl_rows = [ctrl_header]
        for ctrl in ctrls:
            score_val = _effective(ctrl)
            numeric   = _NUMERIC_SCORE.get(score_val, 0.0)
            _, s_hex  = SCORE_COLOR_MAP.get(score_val, (BLACK, "#000000"))
            # Overrides keep an audit trail: show the analyst verdict with
            # the original AI score alongside it
            if ctrl.get("analyst_score"):
                result_markup = (
                    f'<b><font color="{s_hex}">{score_val}</font></b>'
                    f'<font color="{SLATE_HEX}" size="7">  analyst · AI: {ctrl.get("score", "?")}</font>'
                )
            else:
                result_markup = f'<b><font color="{s_hex}">{score_val}</font></b>'
            ctrl_rows.append([
                Paragraph(ctrl.get("control_id", ""), body_style),
                Paragraph(ctrl.get("title", ""), body_style),
                Paragraph(result_markup, body_style),
                Paragraph(f"{numeric * 100:.0f}%", body_style),
            ])

        ctrl_table = Table(
            ctrl_rows,
            colWidths=[0.9 * inch, 3.5 * inch, 1.7 * inch, 0.9 * inch],
        )
        ctrl_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1,  0), DARK_BLUE),
            ("TEXTCOLOR",     (0, 0), (-1,  0), WHITE),
            ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ("GRID",          (0, 0), (-1, -1), 0.5, BORDER_GRAY),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        elements.append(ctrl_table)

        # Evidence & reasoning blocks — directly under the table, no duplicate ID header
        for ctrl in ctrls:
            evidence  = (ctrl.get("evidence_quote") or "").strip()
            reasoning = (ctrl.get("reasoning") or "").strip()
            if not evidence and not reasoning:
                continue

            box_rows = []
            if evidence:
                box_rows.append([
                    Paragraph(
                        f'<b><font color="{BLUE_HEX}">Evidence:</font></b>'
                        f'  {evidence[:400]}',
                        small_style,
                    )
                ])
            if reasoning:
                box_rows.append([
                    Paragraph(
                        f'<b>Reasoning:</b>  {reasoning[:400]}',
                        small_style,
                    )
                ])

            ev_table = Table(box_rows, colWidths=[EV_W])
            ev_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GRAY),
                ("BOX",           (0, 0), (-1, -1), 0.5, BORDER_GRAY),
                ("LEFTPADDING",   (0, 0), (-1, -1), 24),   # visual indent
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
                ("TOPPADDING",    (0, 0), (-1,  0), 7),
                ("BOTTOMPADDING", (0, -1),(-1, -1), 7),
                ("TOPPADDING",    (0, 1), (-1, -1), 4),
            ]))
            elements.append(Spacer(1, 3))
            elements.append(ev_table)

        elements.append(Spacer(1, 12))

    # ─────────────────────────────────────────────────────────────────────
    # 5. VENDOR FOLLOW-UP QUESTIONS (when generated)
    # ─────────────────────────────────────────────────────────────────────

    follow_ups = (assessment.get("follow_up_questions") or {}).get("questions", [])
    if follow_ups:
        elements.append(Paragraph("Recommended Vendor Follow-up Questions", section_title_style))
        elements.append(Paragraph(
            "One question per control that did not fully pass — ready to send "
            "to the vendor to close the evidence gaps.",
            small_style,
        ))
        elements.append(Spacer(1, 6))
        fu_rows = []
        for i, q in enumerate(follow_ups, start=1):
            fu_rows.append([Paragraph(
                f'<b>{i}. [{_sanitize(q.get("control_id", ""))}]</b>  '
                f'{_sanitize(q.get("question", ""))}',
                body_style,
            )])
        fu_table = Table(fu_rows, colWidths=[PAGE_W])
        fu_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GRAY),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER_GRAY),
            ("LINEBELOW",     (0, 0), (-1, -2), 0.5, BORDER_GRAY),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(fu_table)
        elements.append(Spacer(1, 12))

    # ─────────────────────────────────────────────────────────────────────
    # 10. STYLED FOOTER DISCLAIMER
    # ─────────────────────────────────────────────────────────────────────

    elements.append(Spacer(1, 10))
    footer_data = [[Paragraph(
        f"Generated by VendorShield  •  {framework_name}"
        f"  •  Confidential  •  {date_str}",
        footer_style,
    )]]
    footer_table = Table(footer_data, colWidths=[PAGE_W])
    footer_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), FOOTER_GRAY),
        ("LINEABOVE",     (0, 0), (-1,  0), 1, DIVIDER_GRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(footer_table)

    # Build
    doc.build(elements, onLaterPages=later_pages)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info(
        f"Generated PDF report for '{vendor_name}' — {len(pdf_bytes)} bytes"
    )
    return pdf_bytes


# ── Email Sending ─────────────────────────────────────────────────────────────


def send_report_email(to_email: str, assessment: dict) -> dict:
    """Generate a PDF report and email it via Resend.

    Args:
        to_email: Recipient email address.
        assessment: Full assessment dict.

    Returns:
        {"success": True, "message_id": "..."} on success, or
        {"success": False, "error": "..."} on failure.
    """
    settings = get_settings()

    if not settings.resend_api_key:
        return {"success": False, "error": "RESEND_API_KEY is not configured"}

    resend.api_key = settings.resend_api_key

    vendor_name   = assessment.get("vendor_name", "Unknown Vendor")
    overall_score = assessment.get("overall_score", 0)
    risk          = _risk_label(overall_score)
    risk_col_hex  = _risk_hex(overall_score)
    domain_scores = assessment.get("domain_scores", {})

    # Generate PDF
    try:
        pdf_bytes = generate_pdf_report(assessment)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        return {"success": False, "error": f"PDF generation failed: {str(e)}"}

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    # Build domain rows for the HTML email body
    domain_rows_html = ""
    for d_name, d_score in domain_scores.items():
        d_risk = _risk_label(d_score)
        d_col  = _risk_hex(d_score)
        domain_rows_html += (
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;'>{d_name}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:center;'>"
            f"{d_score:.0f} / 100</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:center;'>"
            f"<span style='color:{d_col};font-weight:bold;'>{d_risk}</span></td>"
            f"</tr>"
        )

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#1e3a5f;padding:24px 20px;text-align:center;border-radius:8px 8px 0 0;">
        <h1 style="color:#ffffff;margin:0;font-size:24px;">VendorShield</h1>
        <p style="color:#cdd5e0;margin:6px 0 0;font-size:14px;">Vendor Risk Assessment Report</p>
      </div>
      <div style="height:3px;background:#2563eb;"></div>
      <div style="background:#f8fafc;padding:24px 20px;text-align:center;border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb;">
        <p style="color:#374151;margin:0 0 4px;font-size:13px;">Vendor</p>
        <h2 style="color:#111827;margin:0 0 16px;font-size:20px;">{vendor_name}</h2>
        <div style="display:inline-block;background:white;border-radius:12px;padding:16px 32px;box-shadow:0 1px 3px rgba(0,0,0,0.1);border-left:4px solid {risk_col_hex};">
          <p style="font-size:48px;font-weight:bold;color:{risk_col_hex};margin:0;">{overall_score:.0f}</p>
          <p style="font-size:12px;color:#6b7280;margin:2px 0 0;">/ 100</p>
        </div>
        <p style="margin:12px 0 0;">
          <span style="background:{risk_col_hex};color:white;padding:4px 14px;border-radius:12px;font-size:13px;font-weight:600;">
            {risk} RISK
          </span>
        </p>
      </div>
      <div style="padding:20px;border:1px solid #e5e7eb;border-top:none;">
        <h3 style="color:#1e3a5f;margin:0 0 12px;font-size:15px;">Domain Scores</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <tr style="background:#1e3a5f;color:white;">
            <th style="padding:8px 12px;text-align:left;">Domain</th>
            <th style="padding:8px 12px;text-align:center;">Score</th>
            <th style="padding:8px 12px;text-align:center;">Risk</th>
          </tr>
          {domain_rows_html}
        </table>
      </div>
      <div style="background:#f9fafb;padding:16px 20px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;">
        <p style="color:#9ca3af;font-size:11px;margin:0;text-align:center;">
          Full control breakdown and evidence are attached as a PDF.<br/>
          This report was generated by VendorShield — AI-powered vendor risk assessment.
        </p>
      </div>
    </div>
    """

    subject = (
        f"VendorShield Risk Report — {vendor_name} ({risk}: {overall_score:.0f}/100)"
    )

    try:
        response = resend.Emails.send({
            "from": "VendorShield <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
            "attachments": [
                {
                    "filename": f"VendorShield_Report_{vendor_name.replace(' ', '_')}.pdf",
                    "content": pdf_b64,
                    "content_type": "application/pdf",
                }
            ],
        })

        message_id = (
            response.get("id", "") if isinstance(response, dict)
            else getattr(response, "id", "")
        )
        logger.info(
            f"Report emailed to {to_email} for '{vendor_name}' — "
            f"message_id={message_id}"
        )
        return {"success": True, "message_id": message_id}

    except Exception as e:
        logger.error(f"Resend email failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
