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
