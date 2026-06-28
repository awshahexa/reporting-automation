# Project Anchored Summary

## Goal
Daily automatic sync of tracker Excel into site database with audit trail, continuous PDF extraction via hot folder watchdog, and SharePoint document control pipeline with quality verification before ingestion.

## Constraints & Preferences
- SQLite for now (portable to PostgreSQL after schema finalized)
- All Python deps: PyMuPDF, openpyxl, python-pptx, watchdog, opencv-python, numpy, pytesseract, Pillow, easyocr, transformers (TrOCR), torch, torchvision, scikit-image, shapely, opencv-python-headless, fpdf2; Chart.js + SheetJS on dashboard via CDN
- Dashboard: Python `http.server` + `ThreadingTCPServer` on localhost:8080 — no Flask or external web framework
- SharePoint via Microsoft Graph API (future — needs Azure App registration); local `sharepoint_sim/` fallback
- Audit must log ALL field changes; unauthorized date changes flagged as alerts
- Milestone completion driven by tracker actual dates, not document uploads
- Quality verification runs during document intake: hot_folder → verify → Submit/[DocType]/ (pass) or _failed/ (fail)
- Blur detection via Laplacian variance (OpenCV); threshold configurable per doc type
- OCR fallback (EasyOCR → pytesseract) for scanned image PDFs when text extraction < 50 chars; EasyOCR is primary, pytesseract is fallback
- New deps: easyocr, transformers (TrOCR), torch, torchvision, scikit-image, shapely, opencv-python-headless, fpdf2

## Progress
### Done (Session 2026-06-25) — Dashboard Fixes
- **Bug 1 — `/api/alerts` fixed**: Was returning empty array (loop body had only `continue`). Now generates real alerts: high for milestones missing docs (from Review scan), medium for sites stuck in Pending_Visual_Check, info for recent tracker changes.
- **Bug 2 — `/api/audit` fixed**: Was returning milestone_status rows instead of audit_log. Now queries `audit_log` table via new `get_audit_log()` method. Also added `log_audit_event()` for future event recording.
- **Bug 3 — `POST /api/validate` fixed**: Now deletes orphaned `.issues` sidecar file after moving PDF from PV to Review.
- **Bug 4 — `_api_site_detail` fixed**: Was hardcoding `all_docs_uploaded: True` and `missing_docs: []`. Now compares actual uploaded doc types against milestone requirements (CC: PO/DN/BL/PL/TSSR/SATP; PAC: PO/MOP/SMR/CC/PAF; FAC: PO/PAF/FAF).
- **Bug 5 — `_api_pending_validate` fixed**: Was skipping sites with only `.issues` files (no PDF). Now detects orphaned `.issues` entries and shows them as "PDF not found" rows in PMC Validate tab for reconciliation.
- **Bug 6 — Bottleneck pipeline fixed**: Was showing only 2 stages (Tracker Imported, Documents Uploaded). Now shows 5 real pipeline stages: Hot Folder, Pending Visual Check, Review, Approve, Failed — with actual file counts.
- **Bonus — `_api_date_changes_summary` fixed**: Was returning raw array from DB. Frontend expected `{total, overwrites, additions}` object. Now aggregates and returns correct structure.
- **PMC Validate tab UI updated**: Handles `file_missing` flag — shows red "FILE MISSING" badge, disables Validate button for missing PDFs.
- **PV discrepancy reconciled**: Removed 5 orphaned `.issues` files (CHWA, LODGE, PDGN, PPTK, UMWW — SATPs already in Review). Cleaned hundreds of empty CC/PAC/FAC subdirectories. PV now has 2 clean entries (YPAS, HOCK) with both PDF + .issues.

### Done (Session 2026-06-24)
- **Multi-node filename expansion**: `_expand_multi_node()` detects `&` in any filename segment, creates single-node copies, deletes original, and recursively processes each copy. Handles both prefix form (`RNC&TRUNK_SITE_DOCTYPE.pdf`) and node-type position (`DOCTYPE_SITE_RNC&TRUNK_DATE.pdf`).
- **Cross-check failures → Pending_Visual_Check**: Changed from routing to `_failed/` to `Pending_Visual_Check/[site]/[ms]/`. Status returned as `pending_visual`. `.issues` sidecar JSON saved alongside PDF with issues details.
- **PMC Validate dashboard tab**: New tab listing PV files with clickable PDF links, Related Docs badges (all other CC docs in Review), Issues column, green Validate button.
- **API endpoints**: `GET /api/pending_validate`, `POST /api/validate`, `GET /api/view_file`.
- **`POST /api/validate` moves file to Review** without re-running cross-check (PMC approval overrides automation).
- **Verification tables backfilled**: 114 Review → `passed`, 22 failed → `failed`, 7 PV → `manual_review`. Verification summary now shows real counts (PO:10, DN:9, BL:10, PL:9, TSSR:10, SATP:10, CC:10, FT:10, CLAIM_FORM:18, PAF:5, SMR:1).
- **Auto-rename stores verification in DB**: `process_file()` now calls `db.upsert_verification()` after `verify_document()`.
- **Salvaged files**: `BL_DMSC_RNC&TRUNK` → split+Review; `PL_DMSC_RNC&TRUNK` → split+Review; `PO_DMSC_RNC&TRUNK` → split, cross-check bypassed, manually moved to Review; `ACC_HOCK_PO.pdf` → auto-renamed to `PO_HOCK_ACC_20260624.pdf` → Review/HOCK/{CC,PAC,FAC}/; 6 SATPs → _failed to Pending_Visual_Check.
- **Backup created**: `backup_20260624_011746.zip` (980.2 MB).

### Done (Session 2026-06-23)
- **Cross-check site label per doc type**: `cross_check_cc_docs()` updated with per-doc-type site label checks per user spec:
  - TSSR/SATP: NMS LRD field value = site code
  - PO: SACOFA LRD (Remark box last page) = site code
  - PL: "Site:" label = site code
  - FT: Node Name format `XX.[SITE]-[NODE]-xx-xxxx` = site code
  - DN: "Site ID" label = site code
  - BL: exempted (no site label check)
- **`rstip` → `rstrip` typo fixed** on line 876 (`rstip` would crash on non-ASCII strings)
- **`_auto_rename` bug fixed**: `_parse_filename()` could match 4-part names with invalid doc type (e.g. `ACC_DN_APONG_20260623.pdf`), causing early return without rename → Unknown document type. Now validates parsed doc type against valid list before treating as parseable.
- **Backup created**: `backup_20260623_121446.zip` (13.8 MB)
- **`sp-approve-ready`** now shows CrossChk column (PASS/FAIL) for CC milestones
- **`sp-approve`** refused if cross-check fails for CC milestones
- **TrOCR upgraded** to `microsoft/trocr-large-handwritten` (1.3B params)
- **`_rule_handwritten_date_check`** now soft: flags `⚠ REVIEW REQUIRED`
- **Client notifications**: PDF (fpdf2) + SMTP email via Gmail App Password

### Done (prior)
- **Verification module** (`agents/verification.py`): per-doc-type validation of dates, signatory chain, and reference numbers. 11 verification tables (verification_po, dn, bl, pl, satp, mop, smr, tssr, cc, ft, claim_form) each with sitename as PRIMARY KEY. Hooked into `extraction_engine.py` before DB insert.
- **Dashboard Verification tab**: summary cards per doc type (green/red), filterable table by doc type + status, failed rows highlighted red with issues.
- **Verification CLI**: `python run.py verify` (batch-verify all existing docs), `python run.py verify-status` (summary counts).
- **API endpoints**: `/api/verification` (filtered records, 500 limit), `/api/verification_summary` (per-doc-type counts).
- **Submit pipeline** (`SubmitAgent` in `sharepoint_manager.py`): dedicated to Sites Document Working folder; `hot_folder/` + `_failed/` under `Working/Sites Document/Submit/`; watchdog support; batch and continuous modes.
- **`sp-setup` now creates hot_folder + _failed** under every Working folder (PMC, Project, Sites Document).
- **TSSR filenaming**: `[SITENAME]_TSSR_[NODETYPE]_[YYYYMMDD].pdf` (sitename first, not doc type first); `_identify_doc_type()` updated to handle both old and new formats.
- **TSSR quality rules**:
  - `_rule_tssr_content`: filename sitename must match document's **NMS LRD field value** (not SITE NAME); all 7 required fields must have values; lat/lon label must exist; OCR fallback for scanned images.
  - `_rule_no_blurry_pages`: renders each page at 100 DPI → Laplacian variance → flags pages below threshold (default 1000).
  - `_rule_min_photos_per_category`: groups pages by section heading (detects `X.Y` patterns or keyword-matched titles); counts photo-like images (>=200x200 px) per group; each group must have ≥ 2 photos. Page 1 excluded.
- **SATP quality rules** (`_rule_satp_content`): sitename match (NMS LRD field), required fields (SITE NAME, SITE OWNER, NMS LRD, LAT/LONG), signing page detection (SATP INFO heading + Prepared by/Verified by/Date), sign-off date validity (not in future). Runs via OCR (scanned doc). No photo count rule (SATP is single-image-per-page scanned doc).
- **`_rule_has_text` updated**: OCR fallback via pytesseract for ALL scanned documents (when text extraction < 50 chars).
- **Photo count rule**: grouped by section heading; `_rule_min_photos_per_category` static method in `sharepoint_manager.py`
- **Dashboard HTML** updated: Verification tab inserted between Audit and Bottleneck; filter controls.
- **`run.py` updated**: 4 new submit commands (`sp-submit-status`, `sp-submit-process`, `sp-submit-verify`, `sp-submit-watch`); `verify` and `verify-status` commands.
- **Quality rules framework**: `self.quality_rules` dict in `__init__`; default rules (pdf valid, has text, file naming) run on all docs; doc-type-specific rules added per type.
- **Milestone document readiness validation**: `progress_sync.py:check_readiness()` validates all required docs exist per site+milestone. Flags milestones marked "Completed" but missing required docs. CLI: `python run.py milestone-check [site_code] [milestone]` supports per-site or per-milestone filtering.
- **Sites Document folder restructuring**: Changed from flat doc-type subfolders to `[SITE]/[MILESTONE]/` layout. Working: Submit (hot folder)/ → Review/[SITE]/[MS]/ → Approve/[SITE]/[MS]/. Archive mirrors Approve structure.
- **Content quality rules for all 13 doc types**: PO (vendor/date/site/PO no), DN (DN no/customer/date/site/signature zone), BL (shipper/consignee/ports/vessel), MOP (heading/version/date/site/signatory), CC (Commissioning Cert heading/NMS LRD/signatory), FT (Functionality Test heading/Node Name/date/signatory), PAC/PAF (Provisional Acceptance Cert heading/NMS LRD/signatory), FAF (Final Acceptance heading/site/signatory). All rules OCR-tolerant for scanned docs. Tested PASS on DGAN docs for PO, DN, BL.

### Done (Session current - 2026-06-22)
- **WBS tracker sync implemented** (Option 3 Hybrid): existing parser handles new WBS format correctly (sheet `data`, readable activity names from sub-header rows). Verified across all 3 tracker files: ACC (920 sites), IPCore (15 sites), Trunk (83 sites).
- **Milestone derivation logic** added to `sync_tracker_file()`: CC = `Local Commissioning` has `actual end time`; PAC = `(Preliminary/Provisional) Acceptance Certification` has `status=Completed` or `actual end time`; FAC = `FAC Approval` has `actual end time`. Results: CC=581 Completed / 373 Not started, PAC=33 Completed / 921 Not started, FAC=0 Completed.

### Blocked
- SharePoint Graph API integration blocked — requires Azure App registration + service account from Sacofa IT (Tenant ID, Client ID, Client Secret, Site URL).

## Milestone → Required Documents
| Milestone | Required Documents |
|-----------|-------------------|
| **CC** | PO, DN, BL, PL, TSSR, SATP |
| **PAC** | PO, MOP, SMR, CC, PAF (PAC Approval Form) |
| **FAC** | PO, PAF (PAC Acceptance Form), FAF (FAC Acceptance Form) |

New doc type codes added: `PAF` (PAC Approval/Acceptance Form), `FAF` (FAC Acceptance Form).

## Key Decisions
- **NMS LRD field value** = sitename for TSSR filename (not the SITE NAME field on the form)
- **TSSR filenaming standard**: `[SITENAME]_TSSR_[NODETYPE]_[YYYYMMDD].pdf` — sitename first (deviates from older doc-type-first convention for other doc types)
- **Quality verification gates document intake**: hot_folder → verify → pass → Submit/[DocType]/; fail → Submit/_failed/; docs already in Submit folders can be batch-verified (report only, no move)
- **Blur threshold** default = 1000 Laplacian variance at 100 DPI (catches truly blurry pages, not just light-content text pages)
- **Validation before DB insert**: extracted doc fields verified before insert; approval status stored in verification_* tables regardless of pass/fail
- **SATP photo count rule**: NOT applied to SATP (SATPs are scanned documents with 1 image per page, not photo collages like TSSR)
- **SATP blur threshold = 300, resize_width=500** (scanned documents resized to 500px wide first to normalize across resolutions; threshold=300 catches truly degenerate pages only)
- **SATP signing page detection**: requires BOTH "SATP INFO" heading AND "Prepared by"/"Surveyor name" on same page (ToC also lists "Signing Page - SATP Info" but isn't the actual signing page)

## Next Steps
1. Investigate IPCore CC count discrepancy (3 vs user-expected 22)
2. Obtain SharePoint credentials from Sacofa IT → fill `SHAREPOINT` config → switch `simulate=False`
3. Tune content rules for remaining doc types (CC, FT, PAC/PAF, FAF, MOP, SMR) based on real document samples
4. Configure SMTP in config.py once email server details are available from client

---

## RESUME ANCHOR — Session 2026-06-18 (Latest Session)

### Session Keyword: `resume_dn_zte_fix`

### What We Did
- **Pipeline animation fixed**: shifted main row down to y=0.3, rules above verify box, removed dashboard, widened QUALITY VERIFY & _failed boxes, PMO not PMC
- **`cc_documents_schema.xlsx`** expanded: added PAC Documents, MOP/SMR/PAF verification table sheets (14 sheets total)
- **`data_viewer.html`** created: standalone page at `/data` with Dashboard tab + Data Tables tab (all DB tables as sub-tabs with pagination)
- **File upload to hot folder**: drag-and-drop zone on Dashboard tab, `POST /api/upload` endpoint with manual multipart parser, files land in `sharepoint_sim/Working/Sites Document/Submit (hot folder)/`
- **`sharepoint_vs_onedrive.md`**: analysis doc for 3 deployment scenarios
- **Database cleaned**: `reporting.db` deleted, fresh schema on restart
- **DN_SABE_ACC_20260430.pdf fix**: Chinese-format ZTE DN had no English "SIGNATURE" or "CONSIGNEE" labels
  - `_rule_dn_content`: added 3rd fallback — Receiver/Pick-up + full name + date
  - `_rule_has_signature`: added OCR pass 2 — detects Malaysian full names (ANAK/BIN/BINTI) + date as signature evidence
  - Both rules now pass on this document
- **Handwriting OCR module** (`agents/handwriting_ocr.py`): EasyOCR + TrOCR integration for handwritten date/name extraction
  - `extract_text()`: primary OCR fallback (EasyOCR → pytesseract) in `_rule_has_text` and `auto_recognize`
  - `extract_handwritten_dates()`: detects DATE: labels on signing pages, crops adjacent area, extracts handwritten dates
  - `has_signature_zone()`: EasyOCR-based signature zone detection (Pass 3 in `_rule_has_signature`)
  - `_rule_handwritten_date_check`: replaced pytesseract PSM 6 with EasyOCR+TrOCR for date field detection
  - Lazy-loaded (models only imported on first use)
  - Replaces pytesseract as primary OCR engine for scanned documents
- **New deps**: easyocr, transformers (TrOCR), torchvision, opencv-python-headless, scikit-image, shapely

### Files Modified
- `pipeline_scene.py` — animation layout fixes
- `cc_documents_schema.xlsx` — added PAC, MOP, SMR, PAF sheets
- `data_viewer.html` — new standalone data viewer with upload
- `agents/dashboard_server.py` — `/data` route, `do_POST` for `/api/upload`
- `agents/sharepoint_manager.py` — DN content rule expanded, signature rule OCR pass 2
- `sharepoint_vs_onedrive.md` — new deployment analysis doc

### Relevant Files
- `agents/sharepoint_manager.py:1499` — DN content rule signature zone (3 fallbacks)
- `agents/sharepoint_manager.py:828` — `_rule_has_signature` OCR pass 2

### Resuming
Use keyword `resume_dn_zte_fix` to load this session anchor.

---

## RESUME ANCHOR — Session 2026-06-19 (This Session)

### Session Keyword: `resume_polk_single_month`

### What We Did
- **Crop-based EasyOCR fallback** added to `extract_handwritten_dates()` in `handwriting_ocr.py:330-384`: when full-page spatial detection fails to yield a parsed date, run EasyOCR on the enhanced crop region to catch faint/small handwritten characters that the full-page pass misses.
- **3-stage pipeline for faint handwriting**:
  1. Adaptive Gaussian thresholding (`cv2.adaptiveThreshold`) brings out faint ink
  2. 3-pass majority voting stabilizes EasyOCR non-determinism
  3. Year padding (`6` first) handles incomplete year detection (e.g., `202` → `2026`)
- **Letter-to-digit conversion** via `_clean_digit`: EasyOCR reads `01` as `O1` — the `O` is now converted to `0` before digit extraction
- **Confidence threshold 0.05**: low enough to catch faint real text (conf=0.092) but filters zero-confidence noise (conf=0.000)
- **POLK SATP page 3 Date #2**: `26/01/2026` successfully extracted (was `''` before)
- **`Counter` import moved to module level** to avoid repeated imports in loop

### Files Modified
- `agents/handwriting_ocr.py` — crop fallback with adaptive threshold, multi-pass voting, `_clean_digit` conversion, year padding

### Resuming
Use keyword `resume_polk_single_month` to load this session anchor.

---

## RESUME ANCHOR — Session 2026-06-22 (This Session)

### Session Keyword: `resume_wbs_hybrid`

### What We Did
- **Auto-trigger notification**: `_notify_if_ready()` hooked into `process_file()` — pipeline auto-generates notification PDF + email on completion; refactored `cmd_notify_ready()` to share same helper
- **Validation rules matrix v5**: removed `_rule_handwritten_date_check`, added FAF column (12 doc types), added PAF + FAF content rules, re-indexed 1–21
- **TSSR site_code bug**: `_parse_filename()` in both `extract_base.py` and `extraction_engine.py` fixed to detect sitename-first format (`SITENAME_TSSR_NODETYPE_DATE.pdf`) — no longer incorrectly sets site_code="TSSR"
- **Dashboard Audit**: date changes section with summary cards (total/overwrites/additions), UNAUTHORIZED (red) / NEW (green) badges, `/api/date_changes_summary` endpoint
- **Tracker format analyzed**: all 3 new WBS tracker files mapped — `WPC*|AC*|field_type` column headers, readable names in sub-rows, sheet `data`
- **Option 3 Hybrid agreed**: WBS activities → `site_activities`, milestone derivation from WP `actual_end_date` (WP12000=PAC, WP12201=FAC)

### Files Modified
- `agents/sharepoint_manager.py` — `_notify_if_ready()` in `process_file()`
- `agents/database.py` — `get_unauthorized_date_changes()`, `get_date_changes_summary()`
- `agents/dashboard_server.py` — `/api/date_changes_summary`
- `dashboard.html` — Audit tab date changes section
- `agents/extract_base.py:15` — TSSR sitename-first detection fix
- `agents/extraction_engine.py:186` — TSSR sitename-first detection fix
- `export_rules.py` — validation rules matrix v5 export
- `validation_rules_matrix_v5.xlsx` — updated rule matrix file

### Resuming
Use keyword `resume_wbs_hybrid` to load this session anchor.

---

## Personal Project — XAUUSD Scalp EA

### EA File
`personal/XAUUSD_Scalp_Breakout.mq5` (also copied to MT5 Experts folder)

### Strategy: Asian Range Breakout + Pullback Scalping
- **Timeframe**: M1-M5 entries, M15 EMA 20/50 trend filter
- **Sessions**: London (7-16 UTC) + NY (12-22 UTC) only; Asian tracks range only
- **Indicators**: EMA 20/50, RSI(14), ATR(14)
- **Entries**: Breakout of Asian high/low + pullback to EMA in trend direction
- **SL/TP**: Dynamic — 1.5× ATR / 2.0× ATR
- **Risk**: Auto-compounding (fixed % of balance per trade)
- **Guardrails**: Max 3 trades/session, 2% daily loss, spread filter
- **Trailing**: ATR-based, activates at 1.0× ATR profit

### First Test
- Run live starting Monday on XAUUSD
- Review results after 1 week

### AGENTS.md update: 2026-06-21

## Cross-Doc Validation
- **`sp-cross-check <SITE>`**: validates PO+DN+PL for same site using content (not just filename)
  - Site name cross-check: PO and PL must have exact site code in content; DN allows partial match (e.g. `GAN` for `DGAN`)
  - PO# cross-check: PO# from PO doc must appear in PL; DN is optional
  - BL excluded (shipping doc, rarely has site/PO content)
  - Item-level matching skipped (scanned table OCR unreliable)
- **TrOCR upgraded** to `microsoft/trocr-large-handwritten` (1.3B params)
- **`_rule_handwritten_date_check`** added to SATP rules; pytesseract fallback for DATE: label detection; expanded page range (last 10 + first 5 pages)
- **Timing added** to `verify_document()`: per-rule `time_sec` and `total_time_sec` in results
- **`_rule_handwritten_date_check`** now soft: flags `⚠ REVIEW REQUIRED` when dates can't be detected (non-blocking, needs physical review)

### AGENTS.md update: 2026-06-19

## Sites Document Folder Structure (NEW)
```
Working/Sites Document/
├── Submit (hot folder)/   ← files land here
│   └── failed/            ← quality check failures
├── Review/
│   └── [SITE_CODE]/
│       ├── CC/            ← PO, DN, BL, PL, TSSR, SATP
│       ├── PAC/           ← PO, MOP, SMR, CC, PAF
│       └── FAC/           ← PO, PAF, FAF
└── Approve/               ← (same structure as Review)
    └── [SITE_CODE]/
        ├── CC/
        ├── PAC/
        └── FAC/

Archive/Sites Document/     ← mirrors Approve, no stages
    └── [SITE_CODE]/
        ├── CC/
        ├── PAC/
        └── FAC/
```

### Pipeline Flow
| Step | Action | Trigger |
|------|--------|---------|
| Submit → Review | Quality check → route to `Review/[SITE]/[MS]/` | Auto (file lands in hot folder) |
| Review → Approve | One-shot move of entire milestone folder | PMC (`sp-approve <SITE> <MS>`) |
| Approve → Archive | Move milestone folder to Archive | Auto (archive cycle) |

### New CLI Commands
- `python run.py sp-review-status` — show Review folder readiness per site+milestone
- `python run.py sp-approve-ready` — list milestones with all docs present, ready for PMC approval
- `python run.py sp-approve <SITENAME> <MILESTONE>` — PMC one-shot approval (Review → Approve)

## Critical Context
- **Database state**: 958 sites (ACC=867, ACC+TRUNK=49, TRUNK=17, IPCORE+RNC+TRUNK=6, RNC+TRUNK=5, IPCORE=5, ACC+RNC+TRUNK=3, RNC=2, ACC+IPCORE+TRUNK=2, IPCORE+RNC=1, ACC+IPCORE+RNC+TRUNK=1); CC Completed=577 + 9 RNC, Not started=379 + 9 RNC; PAC+FAC all Not started
- **Processing state**: Hot:0, Review:~109, Failed:~22, Pending_Visual:7 (but only 2 actual PDFs: YPAS, HOCK; 5 others have .issues only)
- **Failed docs breakdown**: ~18 Claim Forms + Invoices (non-standard filenames), 1 FT_DMSC_TRUNK (blurry), 1 JKR (non-standard)
- **PMC Validate tab**: Lists PV files with cross-check issues. APONG SATP validated via test → Review/APONG/CC/
- **Auto-rename flow**: `ACC_HOCK_PO.pdf` (3 parts, no date) → sitename-first format detected → `PO_HOCK_ACC_YYYYMMDD.pdf`
- **`_auto_rename` handles NODETYPE_SITE_DOCTYPE.pdf**: 3-part filenames without dates detected via sitename-first format check
- **`_expand_multi_node` scans all parts for `&`**: Not just `parts[0]`. Handles `BL_DMSC_RNC&TRUNK_20260623.pdf` (ampersand in parts[2]) and `RNC&TRUNK_DMSC_BL.pdf` (ampersand in parts[0]).
- **Verification summary populated**: PO:10, DN:9, BL:10, PL:9, TSSR:10, SATP:10 (8 passed, 2 manual_review), CC:10, FT:10, CLAIM_FORM:18 (all failed), PAF:5, SMR:1.
- **Three states in pipeline**: `passed` → Review/, `manual_review` → Pending_Visual_Check/, `failed` → _failed/
- **sp-visual-approve <S> <M>**: CLI to move from Pending_Visual_Check to Review

## Relevant Files
- `agents/sharepoint_manager.py` — `_expand_multi_node()` (line ~1053), `process_file()` (calls `_expand_multi_node`, `upsert_verification` after quality check), cross-check routing to Pending_Visual_Check with `.issues` sidecar, `_auto_rename` handles NODETYPE_SITE_DOCTYPE.pdf
- `agents/dashboard_server.py` — `_api_pending_validate` (lists PV files + related docs), `_api_validate` (POST — moves file to Review), `_api_view_file` (GET — serves PDF inline)
- `dashboard.html` — PMC Validate tab (`renderPmcValidate`), `validateDoc()` function, Related Docs column
- `agents/database.py` — `upsert_verification()` called during process_file
- `_backfill_verif.py` — backfilled 114 Review + 22 failed + 2 PV verification records
- `agents/handwriting_ocr.py` — EasyOCR + TrOCR integration for handwritten date/signature extraction
- `agents/verification.py` — per-doc-type verification rules, 11 table definitions
- `agents/extraction_engine.py` — verification hook before DB insert
- `agents/config.py` — SharePoint folder definitions, doc type mappings
- `run.py` — `verify`, `verify-status`, `sp-submit-*`, `sp-visual-approve` commands

---

## RESUME ANCHOR — Session 2026-06-25 (This Session)

### Session Keyword: `resume_dn_zte_fix`

### What We Did (This Session)
- **ACC column mapping verified**: CC approval at col 212, PAC at col 259, FAC at col 271 (0-indexed)
- **All trackers resynced (2nd pass)**: Three-state milestones applied. Current: CC=129/646/181 (Completed/Ongoing/Not started), PAC=33/97/826, FAC=0/33/923
- **Site detail — Required Documents table**: Always shows ALL required docs per milestone with Uploaded/Missing badges. Extra docs under "Other Uploaded Documents"
- **Milestone sort enforced server-side**: `_api_site_detail` sorts CC→PAC→FAC
- **Cache-Control no-cache headers**: Added to `_serve_static()`
- **Reject button on PMC Validate tab**: Red Reject button alongside Validate. `POST /api/reject` moves file from PV to `_failed/`, saves `.reject` sidecar with comment + timestamp
- **dashboard_static.html updated**: Mirror changes for Reject button
- **Backup created**: `backup_20260625_074303.zip` (2.15 GB)
- *(Earlier in session)* Fixed 6 dashboard bugs, date_changes_summary, PV reconciled, audit log

### Next Steps (planned)
1. PAC/FAC milestone cross-document validation
2. SharePoint Graph API integration (blocked — needs Azure App registration)
3. Tune OCR content rules for scanned docs
4. Dashboard enhancements (auto-refresh on Bottleneck tab, etc.)

### Resuming
Use keyword `resume_dn_zte_fix` to load this session anchor.
