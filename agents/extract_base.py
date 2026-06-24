"""Base extraction utilities — filename parsing, document type identification."""
import re
from pathlib import Path


def _parse_filename(filename):
    """Parse standard filename: [DOCTYPE]_[SITENAME]_[NODETYPE]_[YYYYMMDD].pdf
    Also handles TSSR sitename-first format: [SITENAME]_TSSR_[NODETYPE]_[YYYYMMDD].pdf
    Returns (doc_type, site_code, node_type, date_str) or (None, None, None, None).
    """
    stem = Path(filename).stem
    parts = stem.split("_")

    # TSSR sitename-first: SITENAME_TSSR_NODETYPE_DATE
    tssr_idx = None
    for i, p in enumerate(parts):
        if p.upper() == "TSSR":
            tssr_idx = i
            break
    if tssr_idx and tssr_idx > 0 and len(parts) >= tssr_idx + 3:
        site_code = parts[0]
        node_type = parts[tssr_idx + 1]
        date_str = parts[tssr_idx + 2]
        if re.match(r"^\d{8}$", date_str):
            return ("TSSR", site_code, node_type, date_str)

    # Standard format: DOCTYPE_SITENAME_NODETYPE_DATE
    if len(parts) >= 4:
        doc_type = parts[0].upper()
        site_code = parts[1]
        node_type = parts[2]
        date_str = parts[3]
        if re.match(r"^\d{8}$", date_str):
            return (doc_type, site_code, node_type, date_str)

    return (None, None, None, None)


def identify_doc_type(filename):
    """Identify document type from filename prefix or content keywords."""
    stem = Path(filename).stem
    parts = stem.split("_")
    if parts:
        dt = parts[0].upper()
        valid = ["PO", "DN", "BL", "PL", "TSSR", "SATP", "MOP", "SMR", "CC", "FT", "PAC", "PAF", "FAF", "CLAIM"]
        if dt in valid:
            return dt
        renames = {"BOL": "BL"}
        if dt in renames:
            return renames[dt]
    return None
