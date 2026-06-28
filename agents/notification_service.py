"""Notification service — generates readiness PDF and sends email via SMTP."""
import smtplib
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from agents.config import SMTP, NOTIFICATION


def generate_readiness_pdf(site_code, milestone, doc_list, cross_check_label, logo_path=None):
    """Generate PDF notification for milestone readiness."""
    out_dir = Path(NOTIFICATION.get("output_dir", "notifications/pdfs"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = out_dir / f"ReadyForApproval_{site_code}_{milestone}_{ts}.pdf"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Milestone Readiness Notification", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Site: {site_code}    Milestone: {milestone}", ln=True)
    pdf.cell(0, 8, f"Cross-Check: {cross_check_label}", ln=True)
    pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)

    # Table header
    pdf.set_font("Arial", "B", 10)
    pdf.cell(60, 8, "Document", border=1)
    pdf.cell(30, 8, "Type", border=1)
    pdf.cell(20, 8, "Pages", border=1)
    pdf.cell(30, 8, "Size (KB)", border=1)
    pdf.cell(40, 8, "Status", border=1)
    pdf.ln()

    pdf.set_font("Arial", "", 10)
    for d in doc_list:
        pdf.cell(60, 7, d.get("filename", "")[:55], border=1)
        pdf.cell(30, 7, d.get("doc_type", ""), border=1)
        pdf.cell(20, 7, str(d.get("pages", "?")), border=1)
        pdf.cell(30, 7, f'{d.get("size_kb", 0):.0f}', border=1)
        pdf.cell(40, 7, d.get("status", ""), border=1)
        pdf.ln()

    pdf.ln(10)
    pdf.cell(0, 8, "Signature:", ln=True)
    pdf.cell(0, 8, "___________________________", ln=True)
    pdf.cell(0, 8, "PMC Representative", ln=True)
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True)

    pdf.output(str(pdf_path))
    return str(pdf_path)


def send_notification_email(site_code, milestone, pdf_path):
    """Send email with PDF attachment via SMTP."""
    if not SMTP.get("host") or not SMTP.get("username"):
        return {"status": "skipped", "message": "SMTP not configured"}

    msg = EmailMessage()
    msg["Subject"] = f"Milestone Ready for Approval - {site_code}/{milestone}"
    msg["From"] = SMTP["from_addr"]
    msg["To"] = SMTP["to_addr"]
    if SMTP.get("cc_addr"):
        msg["Cc"] = SMTP["cc_addr"]

    body = (
        f"Dear PMC,\n\n"
        f"The following milestone is ready for your review and approval:\n\n"
        f"  Site: {site_code}\n"
        f"  Milestone: {milestone}\n\n"
        f"All required documents have been validated and are available in the Review folder.\n"
        f"Please log in to the system to approve.\n\n"
        f"Regards,\nReporting Automation System"
    )
    msg.set_content(body)

    if pdf_path:
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        msg.add_attachment(pdf_data, maintype="application", subtype="pdf",
                           filename=Path(pdf_path).name)

    try:
        with smtplib.SMTP(SMTP["host"], SMTP["port"]) as server:
            if SMTP.get("use_tls"):
                server.starttls()
            server.login(SMTP["username"], SMTP["password"])
            server.send_message(msg)
        return {"status": "sent", "message": f"Email sent to {SMTP['to_addr']}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def send_pmc_validation_email(pv_items):
    """Send HTML email listing items pending manual verification (no attachment)."""
    if not SMTP.get("host") or not SMTP.get("username"):
        return {"status": "skipped", "message": "SMTP not configured"}

    rows_html = ""
    for item in pv_items:
        issues = item.get("issues", "")
        issues_cell = f'<span style="color:#dc2626;font-size:12px">{issues}</span>' if issues else '<span style="color:#22c55e">OK</span>'
        rows_html += f"""<tr>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-weight:600;color:#1f2937">{item.get("site","")}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#374151">{item.get("milestone","")}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#374151">{item.get("doc_type","")}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:12px">{item.get("filename","")}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb">{issues_cell}</td>
</tr>"""

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f3f4f6">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
<tr><td style="background:#1e40af;padding:20px 24px">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="color:#ffffff;font-size:20px;font-weight:700">PMC Validation Required</td></tr>
<tr><td style="color:#93c5fd;font-size:13px;margin-top:4px">Items pending manual verification</td></tr>
</table>
</td></tr>
<tr><td style="padding:24px">
<p style="color:#374151;font-size:14px;line-height:1.6">Dear PMC,</p>
<p style="color:#374151;font-size:14px;line-height:1.6">The following <strong>{len(pv_items)} item(s)</strong> require manual review in the Pending Visual Check folder before they can proceed through the pipeline:</p>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:12px">
<thead>
<tr style="background:#f9fafb">
<th style="padding:10px 12px;text-align:left;font-size:12px;font-weight:600;color:#6b7280;text-transform:uppercase;border-bottom:2px solid #e5e7eb">Site</th>
<th style="padding:10px 12px;text-align:left;font-size:12px;font-weight:600;color:#6b7280;text-transform:uppercase;border-bottom:2px solid #e5e7eb">Milestone</th>
<th style="padding:10px 12px;text-align:left;font-size:12px;font-weight:600;color:#6b7280;text-transform:uppercase;border-bottom:2px solid #e5e7eb">Doc Type</th>
<th style="padding:10px 12px;text-align:left;font-size:12px;font-weight:600;color:#6b7280;text-transform:uppercase;border-bottom:2px solid #e5e7eb">Filename</th>
<th style="padding:10px 12px;text-align:left;font-size:12px;font-weight:600;color:#6b7280;text-transform:uppercase;border-bottom:2px solid #e5e7eb">Issues</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
<p style="color:#374151;font-size:14px;line-height:1.6;margin-top:20px">Please review each item and either <strong style="color:#059669">approve</strong> via <code style="background:#f3f4f6;padding:2px 6px;border-radius:3px;font-size:12px">sp-visual-approve &lt;SITE&gt; &lt;MS&gt;</code> or reject if the content does not meet requirements.</p>
</td></tr>
<tr><td style="background:#f9fafb;padding:16px 24px;border-top:1px solid #e5e7eb">
<p style="color:#9ca3af;font-size:12px;margin:0">Reporting Automation System &middot; Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

    text_body = (
        f"Dear PMC,\n\n"
        f"The following {len(pv_items)} item(s) require manual verification:\n\n"
        + "\n".join(
            f"  {item.get('site','')}/{item.get('milestone','')} - {item.get('doc_type','')} - {item.get('filename','')}"
            + (f"  Issues: {item.get('issues','')}" if item.get("issues") else "")
            for item in pv_items
        ) +
        "\n\nPlease review each item in the Pending Visual Check folder.\n"
        "Use 'sp-visual-approve <SITE> <MS>' to approve once verified.\n\n"
        "Regards,\nReporting Automation System"
    )

    msg = EmailMessage()
    msg["Subject"] = f"PMC Validation Required — {len(pv_items)} Item(s) Pending Manual Verification"
    msg["From"] = SMTP["from_addr"]
    msg["To"] = SMTP["to_addr"]
    if SMTP.get("cc_addr"):
        msg["Cc"] = SMTP["cc_addr"]
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(SMTP["host"], SMTP["port"]) as server:
            if SMTP.get("use_tls"):
                server.starttls()
            server.login(SMTP["username"], SMTP["password"])
            server.send_message(msg)
        return {"status": "sent", "message": f"PMC validation email sent to {SMTP['to_addr']}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
