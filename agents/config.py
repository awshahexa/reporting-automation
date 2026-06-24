from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
HOT_FOLDER = BASE_DIR / "hot_folder"
EXPORTS_DIR = BASE_DIR / "exports"
TRACKER_ARCHIVE_DIR = BASE_DIR / "tracker_archive"
SHAREPOINT_SIM_DIR = BASE_DIR / "sharepoint_sim"

WORKING_FOLDERS = ["PMC Folder", "Project Folder", "Sites Document"]
ARCHIVE_FOLDERS = ["PMC Folder", "Project Folder", "Sites Document"]
FOLDER_STAGES = ["Submit", "Review", "Approve"]

SITES_DOC_AREA = "Sites Document"
SITES_DOC_SUBMIT = "Submit (hot folder)"

MILESTONES = ["CC", "PAC", "FAC"]

MILESTONE_DOCS = {
    "CC": ["PO", "DN", "BL", "PL", "TSSR", "SATP", "FT"],
    "PAC": ["PO", "MOP", "SMR", "CC", "PAF"],
    "FAC": ["PO", "PAF", "FAF"],
}

ALL_DOC_TYPES = ["PO", "DN", "BL", "PL", "TSSR", "SATP", "MOP", "SMR", "CC", "FT", "PAC", "PAF", "FAF", "TSS", "CLAIM"]

DOC_TYPE_KEYWORDS = {
    "PO": ["purchase order", "po no", "p/o no"],
    "DN": ["delivery note", "delivery order", "dn no", "d/n no", "packing list"],
    "BL": ["bill of lading", "bill of landing", "b/l", "shipper"],
    "PL": ["packing list", "packing"],
    "TSSR": ["tssr", "test site", "site survey"],
    "SATP": ["satp", "site acceptance", "surveyor"],
    "MOP": ["mop", "method of procedure"],
    "SMR": ["smr", "site migration"],
    "CC": ["commissioning", "site commissioning"],
    "FT": ["functionality test", "functional test"],
    "PAC": ["provisional acceptance", "preliminary acceptance"],
    "PAF": ["pac approval", "pac acceptance"],
    "FAF": ["fac acceptance", "final acceptance"],
    "CLAIM": ["claim form", "claim"],
}

DOC_TYPE_RENAMES = {
    "BOL": "BL",
    "DN": "DN",
    "PL": "PL",
}

STATUS_VALUES = ["Not started", "Ongoing", "Completed"]
LOGGING_LEVEL = "INFO"
WATCH_INTERVAL_SECONDS = 30

SHAREPOINT = {
    "tenant_id": "",
    "client_id": "",
    "client_secret": "",
    "site_url": "",
    "library_name": "Documents",
    "working_root": "",
    "archive_root": "",
}

SMTP = {
    "host": "smtp.gmail.com",
    "port": 587,
    "use_tls": True,
    "username": "mnizam.wahiddin@gmail.com",
    "password": "btqiswnkxhhqgzvk",
    "from_addr": "mnizam.wahiddin@gmail.com",
    "to_addr": "mshaifulnizam.ahmad@hexamatics.com",
    "cc_addr": "",
}

NOTIFICATION = {
    "company_logo_path": "",
    "output_dir": BASE_DIR / "notifications" / "pdfs",
}
