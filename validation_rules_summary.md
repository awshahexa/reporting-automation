# Document Validation Rules — Executive Summary

## Overview
Every document uploaded into the system is automatically checked for quality before it reaches the Review folder. These checks ensure documents are complete, readable, correctly named, and properly signed.

## Universal Checks (All Document Types)

| Check | What It Means |
|-------|---------------|
| **Valid File** | File must be a readable PDF (not corrupted, has at least 1 page) |
| **Has Content** | Document contains extractable text or is a readable scanned image (OCR fallback) |
| **Correct Filename** | File name follows the standard: `[DOCTYPE]_[SITENAME]_[NODETYPE]_[DATE].pdf` |

## Document-Specific Checks

### CC Milestone Documents

| Document | Extra Checks |
|----------|-------------|
| **PO** (Purchase Order) | No extra checks beyond universal |
| **DN** (Delivery Note) | ✅ Must have a **signature on the last page** |
| **BL** (Bill of Lading) | No extra checks beyond universal |
| **PL** (Packing List) | ✅ Must contain: Reference number, PO number, PO Date, Site name matching file, Prepared By name ✅ Must have a **signature on the last page** |
| **FT** (Factory Test) | ✅ Must have **signatures starting from page 6** (first 5 pages are cover/summary) |
| **TSSR** (Technical Site Survey Report) | ✅ All 7 key fields filled on page 1 (Site Name, Site Owner, Tower ID, Region, Site Structure, Equipment Model, Equipment Function) ✅ Latitude/Longitude must be present ✅ Site code matches filename ✅ No blurry pages ✅ Each section must have at least 1 photo ✅ Must have signatures somewhere in the document |
| **SATP** (Site Acceptance Test Procedure) | ✅ 4 key fields on page 1 (Site Name, Site Owner, NMS LRD, Latitude/Longitude) ✅ Signing page must be present with Prepared By, Verified By, and Date ✅ Sign-off date cannot be in the future ✅ Site code matches filename ✅ No blurry pages ✅ Must have signatures somewhere in the document |

### PAC Milestone Documents

| Document | Extra Checks |
|----------|-------------|
| **PO** (Purchase Order) | No extra checks beyond universal |
| **CC** (Certificate of Completion) | ✅ Must have **signatures somewhere in the document** |
| **MOP** (Method of Procedure) | No extra checks beyond universal |
| **SMR** (Site Measurement Report) | ✅ Must have a **signature on page 2** |

### FAC Milestone Documents

| Document | Extra Checks |
|----------|-------------|
| **PO** (Purchase Order) | No extra checks beyond universal |
| **PAC** (PAC Approval/Acceptance Form) | No extra checks beyond universal |

## Smart Signature Detection
The system intelligently distinguishes between:
- ✅ **Real signatures** — detected as signature images or text blocks
- ❌ **"N/A" placeholders** — automatically ignored (not counted as signatures)
- 📄 **Scanned documents** — uses OCR to find signatures on scanned/printed pages

## Quality Flow
```
Upload → Valid PDF? → Has Text? → Correct Name? → Doc-Type Checks? → Review Folder
         ↓              ↓            ↓               ↓
         ❌ Reject      ❌ Reject    ❌ Reject       ❌ Reject → _failed/ folder
```

Documents that fail any check are moved to the `_failed/` folder with a clear explanation of what went wrong. Only documents that pass all checks reach the Review folder for approval.
