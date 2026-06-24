"""Per-doc-type verification rules — validates dates, signatory chain, reference numbers."""
import re
from datetime import datetime


def verify_document(doc_data):
    """Run verification rules for a document based on its doc_type.
    Returns dict with sitename, status, issues, and rule-level results.
    """
    doc_type = doc_data.get("doc_type", "").upper()
    site_code = doc_data.get("site_code", "")
    result = {
        "sitename": site_code,
        "doc_type": doc_type,
        "status": "passed",
        "issues": [],
        "rules": {},
    }

    validators = {
        "PO": _verify_po,
        "DN": _verify_dn,
        "BL": _verify_bl,
        "PL": _verify_pl,
        "TSSR": _verify_tssr,
        "SATP": _verify_satp,
        "MOP": _verify_mop,
        "SMR": _verify_smr,
        "CC": _verify_cc,
        "FT": _verify_ft,
        "PAC": _verify_paf,
        "PAF": _verify_paf,
        "FAF": _verify_faf,
    }
    validator = validators.get(doc_type)
    if validator:
        validator(doc_data, result)

    if result["issues"]:
        result["status"] = "failed"
    return result


def _check_date(date_str, field_label, result):
    if not date_str:
        return
    try:
        dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        if dt > datetime.now():
            result["issues"].append(f"{field_label} is in the future ({date_str})")
    except (ValueError, TypeError):
        pass


def _check_signatory(name_field, date_field, label, data, result):
    name = data.get(name_field)
    date = data.get(date_field)
    if name and not date:
        result["issues"].append(f"{label}: {name} signed but no date")
    if date and not name:
        result["issues"].append(f"{label}: date present but no signatory name")


def _verify_po(data, result):
    po = data.get("po_number") or data.get("verified_name", "")
    vendor = data.get("vendor") or data.get("verified_designation", "")
    date = data.get("doc_date")
    if not po:
        result["issues"].append("Missing PO number")
    _check_date(date, "PO date", result)
    _check_signatory("verified_name", "verified_date", "Verified", data, result)
    _check_signatory("approved_name", "approved_date", "Approved", data, result)


def _verify_dn(data, result):
    dn = data.get("dn_number") or data.get("verified_name", "")
    date = data.get("doc_date")
    if not dn:
        result["issues"].append("Missing DN number")
    _check_date(date, "DN date", result)
    if data.get("customer"):
        _check_signatory("verified_name", "verified_date", "Verified", data, result)


def _verify_bl(data, result):
    bl = data.get("bl_number")
    date = data.get("doc_date")
    if not bl:
        result["issues"].append("Missing BL number")
    _check_date(date, "BL date", result)
    if not data.get("shipper"):
        result["issues"].append("Missing shipper")
    if not data.get("consignee"):
        result["issues"].append("Missing consignee")


def _verify_pl(data, result):
    pl = data.get("pl_number")
    date = data.get("doc_date")
    if not pl:
        result["issues"].append("Missing PL number")
    _check_date(date, "PL date", result)


def _verify_tssr(data, result):
    date = data.get("doc_date")
    _check_date(date, "TSSR date", result)
    if not data.get("latitude") or not data.get("longitude"):
        result["issues"].append("Missing lat/lon")
    _check_signatory("verified_name", "verified_date", "Verified", data, result)
    _check_signatory("approved_name", "approved_date", "Approved", data, result)


def _verify_satp(data, result):
    date = data.get("doc_date")
    _check_date(date, "SATP date", result)
    _check_signatory("verified_name", "verified_date", "Verified", data, result)
    _check_signatory("approved_name", "approved_date", "Approved", data, result)


def _verify_mop(data, result):
    date = data.get("doc_date")
    _check_date(date, "MOP date", result)
    _check_signatory("prepared_by", "prepared_date", "Prepared", data, result)
    _check_signatory("reviewed_by", "reviewed_date", "Reviewed", data, result)
    _check_signatory("approved_by", "approved_date", "Approved", data, result)


def _verify_smr(data, result):
    date = data.get("doc_date")
    _check_date(date, "SMR date", result)
    _check_signatory("verified_name", "verified_date", "Verified", data, result)
    _check_signatory("reviewed_name", "reviewed_date", "Reviewed", data, result)
    _check_signatory("approved_name", "approved_date", "Approved", data, result)


def _verify_cc(data, result):
    date = data.get("doc_date")
    _check_date(date, "CC date", result)
    _check_signatory("verified_name", "verified_date", "Verified", data, result)
    _check_signatory("approved_name", "approved_date", "Approved", data, result)


def _verify_ft(data, result):
    date = data.get("doc_date")
    _check_date(date, "FT date", result)


def _verify_paf(data, result):
    date = data.get("doc_date")
    _check_date(date, "PAF date", result)
    _check_signatory("verified_name", "verified_date", "Verified", data, result)
    _check_signatory("approved_name", "approved_date", "Approved", data, result)


def _verify_faf(data, result):
    date = data.get("doc_date")
    _check_date(date, "FAF date", result)
    _check_signatory("verified_name", "verified_date", "Verified", data, result)
    _check_signatory("approved_name", "approved_date", "Approved", data, result)
