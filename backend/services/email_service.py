"""
Layer 3: Email & PDF Report Service.

RESPONSIBILITY:
    Generates a professional PDF risk assessment report entirely in memory
    (BytesIO — never touches disk) using ReportLab, and sends it as an
    email attachment via the Resend SDK.

    Two public functions:
    - generate_pdf_report(assessment) → bytes
    - send_report_email(to_email, assessment) → dict

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
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from config import get_settings

logger = logging.getLogger(__name__)

# ── Colour Constants ─────────────────────────────────────────────────────────

GREEN = colors.HexColor("#16a34a")
ORANGE = colors.HexColor("#ea580c")
RED = colors.HexColor("#dc2626")
DARK_BLUE = colors.HexColor("#1e3a5f")
LIGHT_GRAY = colors.HexColor("#f3f4f6")
WHITE = colors.white
BLACK = colors.black

SCORE_COLORS = {
    "PASS": GREEN,
    "PARTIAL": ORANGE,
    "FAIL": RED,
    "NO_EVIDENCE": colors.HexColor("#6b7280"),
}


def _risk_label(score: float) -> str:
    """Return LOW / MEDIUM / HIGH based on score thresholds."""
    if score >= 70:
        return "LOW"
    elif score >= 40:
        return "MEDIUM"
    return "HIGH"


def _risk_color(score: float) -> colors.HexColor:
    """Return green / orange / red based on score thresholds."""
    if score >= 70:
        return GREEN
    elif score >= 40:
        return ORANGE
    return RED


# ── PDF Generation ───────────────────────────────────────────────────────────


def generate_pdf_report(assessment: dict) -> bytes:
    """Generate a professional PDF risk report entirely in memory.

    Args:
        assessment: Dict matching the assessment shape (see module docstring).

    Returns:
        Raw PDF bytes (ready to attach to an email or stream to a client).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    elements: list = []

    vendor_name = assessment.get("vendor_name", "Unknown Vendor")
    overall_score = assessment.get("overall_score", 0)
    domain_scores = assessment.get("domain_scores", {})
    controls = assessment.get("control_results", [])
    created_at = assessment.get("created_at", "")
    risk = _risk_label(overall_score)
    risk_col = _risk_color(overall_score)

    # Parse date
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%B %d, %Y")
    except Exception:
        date_str = created_at[:10] if len(created_at) >= 10 else "N/A"

    # ── Custom styles ────────────────────────────────────────────────────

    header_style = ParagraphStyle(
        "Header",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=WHITE,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    sub_header_style = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        textColor=colors.HexColor("#cdd5e0"),
        alignment=TA_CENTER,
    )
    section_title = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=DARK_BLUE,
        spaceBefore=16,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=BLACK,
        leading=12,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#6b7280"),
        leading=10,
    )

    # ── 1. Header Banner ─────────────────────────────────────────────────

    header_data = [
        [Paragraph("VendorShield", header_style)],
        [Paragraph(f"Vendor Risk Assessment — {vendor_name}", sub_header_style)],
        [Paragraph(f"Generated: {date_str}", sub_header_style)],
    ]
    header_table = Table(header_data, colWidths=[6.5 * inch])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_BLUE),
        ("TOPPADDING", (0, 0), (-1, 0), 20),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 16),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 16))

    # ── 2. Overall Score Card ────────────────────────────────────────────

    score_text = ParagraphStyle(
        "ScoreNum",
        fontName="Helvetica-Bold",
        fontSize=36,
        textColor=risk_col,
        alignment=TA_CENTER,
    )
    risk_text = ParagraphStyle(
        "RiskLabel",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=risk_col,
        alignment=TA_CENTER,
    )
    score_data = [
        [Paragraph("Overall Risk Score", section_title)],
        [Paragraph(f"{overall_score:.0f} / 100", score_text)],
        [Paragraph(f"Risk Level: {risk}", risk_text)],
    ]
    score_table = Table(score_data, colWidths=[6.5 * inch])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 16))

    # ── 3. Domain Scores Table ───────────────────────────────────────────

    elements.append(Paragraph("Domain Scores", section_title))

    domain_header = [
        Paragraph("<b>Domain</b>", body_style),
        Paragraph("<b>Score</b>", body_style),
        Paragraph("<b>Risk Level</b>", body_style),
    ]
    domain_rows = [domain_header]
    for domain_name, domain_score in domain_scores.items():
        d_risk = _risk_label(domain_score)
        d_color = _risk_color(domain_score)
        domain_rows.append([
            Paragraph(domain_name, body_style),
            Paragraph(f"{domain_score:.0f}%", body_style),
            Paragraph(
                f'<font color="{d_color.hexval()}">{d_risk}</font>',
                body_style,
            ),
        ])

    domain_table = Table(domain_rows, colWidths=[3.5 * inch, 1.2 * inch, 1.8 * inch])
    domain_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(domain_table)
    elements.append(Spacer(1, 16))

    # ── 4. Control Breakdown by Domain ───────────────────────────────────

    elements.append(Paragraph("Control Breakdown", section_title))

    # Group controls by domain
    domains_grouped: dict[str, list] = {}
    for ctrl in controls:
        d = ctrl.get("domain", "Other")
        domains_grouped.setdefault(d, []).append(ctrl)

    for domain_name, ctrls in domains_grouped.items():
        elements.append(Paragraph(f"<b>{domain_name}</b>", body_style))
        elements.append(Spacer(1, 4))

        ctrl_header = [
            Paragraph("<b>ID</b>", body_style),
            Paragraph("<b>Title</b>", body_style),
            Paragraph("<b>Result</b>", body_style),
            Paragraph("<b>Score</b>", body_style),
        ]
        ctrl_rows = [ctrl_header]
        _score_map = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0, "NO_EVIDENCE": 0.0}
        for ctrl in ctrls:
            score_val = ctrl.get("score", "NO_EVIDENCE")
            numeric = _score_map.get(score_val, 0.0)
            s_color = SCORE_COLORS.get(score_val, BLACK)
            ctrl_rows.append([
                Paragraph(ctrl.get("control_id", ""), body_style),
                Paragraph(ctrl.get("title", ""), body_style),
                Paragraph(
                    f'<font color="{s_color.hexval()}">{score_val}</font>',
                    body_style,
                ),
                Paragraph(f"{numeric * 100:.0f}%", body_style),
            ])

        ctrl_table = Table(
            ctrl_rows,
            colWidths=[0.9 * inch, 2.8 * inch, 1.4 * inch, 0.8 * inch],
        )
        ctrl_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(ctrl_table)
        elements.append(Spacer(1, 6))

        # Evidence & reasoning per control
        for ctrl in ctrls:
            evidence = (ctrl.get("evidence_quote") or "")[:300]
            reasoning = (ctrl.get("reasoning") or "")[:300]
            if evidence or reasoning:
                cid = ctrl.get("control_id", "")
                elements.append(
                    Paragraph(f"<b>{cid}</b>", small_style)
                )
                if evidence:
                    elements.append(
                        Paragraph(f"<i>Evidence:</i> {evidence}", small_style)
                    )
                if reasoning:
                    elements.append(
                        Paragraph(f"<i>Reasoning:</i> {reasoning}", small_style)
                    )
                elements.append(Spacer(1, 4))

        elements.append(Spacer(1, 8))

    # ── 5. Footer Disclaimer ─────────────────────────────────────────────

    elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
    elements.append(Spacer(1, 8))
    disclaimer = (
        "This report was generated by VendorShield, an AI-powered vendor risk "
        "assessment platform. Scores are derived from automated analysis of "
        "uploaded vendor documentation against NIST SP 800-53 Rev.5 controls. "
        "Results should be reviewed by a qualified security professional before "
        "making business decisions. This report is confidential and intended "
        "solely for the designated recipient."
    )
    elements.append(Paragraph(disclaimer, small_style))

    # Build
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info(
        f"Generated PDF report for '{vendor_name}' — {len(pdf_bytes)} bytes"
    )
    return pdf_bytes


# ── Email Sending ────────────────────────────────────────────────────────────


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

    vendor_name = assessment.get("vendor_name", "Unknown Vendor")
    overall_score = assessment.get("overall_score", 0)
    risk = _risk_label(overall_score)
    risk_col_hex = _risk_color(overall_score).hexval()
    domain_scores = assessment.get("domain_scores", {})

    # Generate PDF
    try:
        pdf_bytes = generate_pdf_report(assessment)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        return {"success": False, "error": f"PDF generation failed: {str(e)}"}

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    # Build domain rows for the HTML email
    domain_rows_html = ""
    for d_name, d_score in domain_scores.items():
        d_risk = _risk_label(d_score)
        d_col = _risk_color(d_score).hexval()
        domain_rows_html += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{d_name}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:center;">{d_score:.0f}%</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:center;">
            <span style="color:{d_col};font-weight:bold;">{d_risk}</span>
          </td>
        </tr>"""

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;">
      <!-- Header -->
      <div style="background:#1e3a5f;padding:24px 20px;text-align:center;border-radius:8px 8px 0 0;">
        <h1 style="color:#ffffff;margin:0;font-size:24px;">VendorShield</h1>
        <p style="color:#cdd5e0;margin:6px 0 0;font-size:14px;">Vendor Risk Assessment Report</p>
      </div>

      <!-- Score Card -->
      <div style="background:#f8fafc;padding:24px 20px;text-align:center;border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb;">
        <p style="color:#374151;margin:0 0 4px;font-size:13px;">Vendor</p>
        <h2 style="color:#111827;margin:0 0 16px;font-size:20px;">{vendor_name}</h2>
        <div style="display:inline-block;background:white;border-radius:12px;padding:16px 32px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
          <p style="font-size:42px;font-weight:bold;color:{risk_col_hex};margin:0;">{overall_score:.0f}</p>
          <p style="font-size:12px;color:#6b7280;margin:2px 0 0;">/ 100</p>
        </div>
        <p style="margin:12px 0 0;">
          <span style="background:{risk_col_hex};color:white;padding:4px 14px;border-radius:12px;font-size:13px;font-weight:600;">
            {risk} RISK
          </span>
        </p>
      </div>

      <!-- Domain Scores -->
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

      <!-- Footer -->
      <div style="background:#f9fafb;padding:16px 20px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;">
        <p style="color:#9ca3af;font-size:11px;margin:0;text-align:center;">
          Full control breakdown and evidence are attached as a PDF.<br/>
          This report was generated by VendorShield — AI-powered vendor risk assessment.
        </p>
      </div>
    </div>
    """

    # Send via Resend
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

        message_id = response.get("id", "") if isinstance(response, dict) else getattr(response, "id", "")
        logger.info(
            f"Report emailed to {to_email} for '{vendor_name}' — "
            f"message_id={message_id}"
        )
        return {"success": True, "message_id": message_id}

    except Exception as e:
        logger.error(f"Resend email failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
