import re, sys
from pathlib import Path
import fitz
import pytesseract
from PIL import Image
import io
import openpyxl

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

REVIEW = Path(r"C:\Users\Apex Asia\Documents\Nizam\Sacofa\Reporting-Automation\sharepoint_sim\Working\Sites Document\Review")
OUTPUT = Path(r"C:\Users\Apex Asia\Documents\Nizam\Sacofa\Reporting-Automation\DN_Extracted_Info.xlsx")

DN_FILES = sorted(REVIEW.glob("**/DN_*.pdf"))

def ocr_page(page, dpi=300):
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang="chi_sim+eng")

def char_sim(a, b):
    """Simple character overlap score (0-100)."""
    a, b = a.upper(), b.upper()
    if len(a) != len(b):
        return 0
    return sum(1 for ca, cb in zip(a, b) if ca == cb) / len(a) * 100

def extract_site_code(text, expected_site):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    expected = expected_site.upper()
    best_candidate = ""
    best_score = 0

    def score(cand):
        if not cand or len(cand) < 2:
            return 0
        c = cand.upper()
        if c == expected:
            return 100
        common = sum(1 for ch in c if ch in expected)
        return common / max(len(c), len(expected)) * 100

    # Strategy 1: XXX-{Trunk,ACC}-MOS pattern (label not required)
    m = re.search(r"\b([A-Za-z0-9]{2,6})-(?:Trunk|ACC)-MOS", text, re.IGNORECASE)
    if m:
        cand = m.group(1).upper()
        s = score(cand)
        if s >= 60:
            return cand
        if s > best_score:
            best_candidate, best_score = cand, s

    # Strategy 2: Near Controller/Account/到站点 labels
    for i, line in enumerate(lines):
        if any(kw in line.upper() for kw in ["CONTROLLER", "ACCOUNT", "控制", "到站点"]):
            for j in range(max(0,i-1), min(len(lines),i+6)):
                for token in re.findall(r"\b([A-Za-z0-9]{3,7})\b", lines[j]):
                    s = score(token)
                    if s >= 80:
                        return token.upper()
                    if s > best_score:
                        best_candidate, best_score = token.upper(), s

    # Strategy 3: Search all tokens for close match
    for line in lines:
        for token in re.findall(r"\b([A-Za-z]{3,6})\b", line):
            s = score(token)
            if s >= 80:
                return token.upper()
            if s > best_score:
                best_candidate, best_score = token.upper(), s

    # Strategy 4: Accept best partial match
    if expected and best_score >= 50:
        return best_candidate

    return ""

def extract_fields(text, filename_site):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    fields = {k: "" for k in ("dn_number","reference_do","po_no","site_doc","date","prepared_by","project")}

    # --- DN Number ---
    for line in lines:
        m = re.search(r"\b(WMY\d{6,})\b", line, re.IGNORECASE)
        if m:
            fields["dn_number"] = m.group(1).strip()
            break
    if not fields["dn_number"]:
        for line in lines:
            m = re.search(r"(?:^|\b)DN\s*([A-Za-z0-9]{8,})", line, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if not any(kw in val.upper() for kw in ["NOTE", "NUMBER"]):
                    fields["dn_number"] = val
                    break

    # --- DO / Reference ---
    for line in lines:
        m = re.search(r"\b(DO[A-Z0-9]{7,})\b", line, re.IGNORECASE)
        if m:
            fields["reference_do"] = m.group(1).strip()
            break

    # --- PO No (only full-length) ---
    for i, line in enumerate(lines):
        if re.search(r"Material\s*Source\s*PO|物料来源|Mane\s*Source", line, re.IGNORECASE):
            for j in range(i, min(i+6, len(lines))):
                m = re.findall(r"(S\d*MY\d{10,}[A-Za-z0-9]*)", lines[j], re.IGNORECASE)
                if m:
                    fields["po_no"] = ", ".join(sorted(set(m)))
                    break
            break
    if not fields["po_no"]:
        for line in lines:
            m = re.findall(r"(S\d*MY\d{10,}[A-Za-z0-9]*)", line, re.IGNORECASE)
            if m:
                fields["po_no"] = ", ".join(sorted(set(m)))
                break

    # --- Site Code ---
    fields["site_doc"] = extract_site_code(text, filename_site)

    # --- Date ---
    for line in lines:
        m = re.search(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})", line, re.IGNORECASE)
        if m and not fields["date"]:
            fields["date"] = m.group(1).strip()
    if not fields["date"]:
        for line in lines:
            m = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", line)
            if m:
                fields["date"] = m.group(1).strip()
                break

    # --- Prepared By ---
    for line in lines:
        m = re.search(r"(?:提货人|Pick\.?up|收货人|Receiver|Consignee|Warehouse\s*Manager)[\s\*]*[:：]?\s*([A-Za-z\s.]+?)(?:\s+\d|\||$)", line, re.IGNORECASE)
        if m:
            val = m.group(1).strip().rstrip(".")
            if val and len(val) > 3 and not re.match(r'^\d+$', val):
                if not any(excl in val.upper() for excl in ["SIGNATURE", "DATE", "PERSON"]):
                    fields["prepared_by"] = val
                    break

    # --- Project ---
    for line in lines:
        if "Sacofa" in line and len(line) > 10:
            fields["project"] = line.strip()
            break
    if not fields["project"]:
        for line in lines:
            if "马来西亚" in line and len(line) > 10:
                fields["project"] = line.strip()
                break

    return fields

def safe_print(k, v):
    if v:
        safe = v.encode('ascii', 'replace').decode('ascii')
    else:
        safe = "N/A"
    print(f"  {k}: {safe}")

def main():
    rows = []
    for idx, pdf_path in enumerate(DN_FILES, 1):
        filename = pdf_path.name
        site_code_from_name = filename.replace("DN_", "").split("_")[0].upper()
        print(f"\n[{idx}] {filename}")

        doc = fitz.open(str(pdf_path))
        all_text = ""
        for page in doc:
            all_text += ocr_page(page)
        doc.close()

        fields = extract_fields(all_text, site_code_from_name)
        site_doc = fields["site_doc"].upper() if fields["site_doc"] else ""

        if site_doc:
            match_status = "MATCH" if site_code_from_name == site_doc else f"NEAR ({site_doc})"
        else:
            match_status = "NOT FOUND"

        safe_print("dn_number", fields["dn_number"])
        safe_print("reference_do", fields["reference_do"])
        safe_print("po_no", fields["po_no"])
        safe_print("site_doc", fields["site_doc"])
        safe_print("date", fields["date"])
        safe_print("prepared_by", fields["prepared_by"])
        safe_print("project", fields["project"])
        safe_print("status", match_status)

        manual_alert = "YES - PMC to validate" if "NEAR" in match_status or "NOT FOUND" in match_status else ""

        rows.append((idx, filename, site_code_from_name,
                     fields["dn_number"], fields["reference_do"],
                     fields["po_no"], fields["site_doc"],
                     fields["date"], fields["prepared_by"],
                     fields["project"], match_status, manual_alert))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DN Extraction"
    headers = ["#", "Filename", "Site Code (Name)", "DN No", "Reference (DO#)",
               "PO No", "Site (Doc)", "Date", "Prepared By", "Project", "Status",
               "Manual Validation Required"]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 32
    wb.save(str(OUTPUT))
    print(f"\nSaved -> {OUTPUT}")
    print(f"Total: {len(rows)} DNs")

if __name__ == "__main__":
    main()
