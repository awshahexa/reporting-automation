"""SharePoint Manager — folder structure, document pipeline, cross-check, quality rules."""
import re, os, shutil, json, sys, hashlib
from pathlib import Path
from datetime import datetime
from functools import partial

from agents.database import DatabaseAgent
from agents.config import (
    SHAREPOINT_SIM_DIR, WORKING_FOLDERS, ARCHIVE_FOLDERS, FOLDER_STAGES,
    SITES_DOC_AREA, SITES_DOC_SUBMIT, MILESTONES, MILESTONE_DOCS,
    ALL_DOC_TYPES, LOGGING_LEVEL, WATCH_INTERVAL_SECONDS,
)


_NO_STAGES = object()


class SharePointManager:
    """Manages SharePoint folder structure: Working (Submit/Review/Approve) and Archive."""

    def __init__(self, simulate=True):
        self.simulate = simulate
        self.db = DatabaseAgent()
        self.working_root = SHAREPOINT_SIM_DIR / "Working"
        self.archive_root = SHAREPOINT_SIM_DIR / "Archive"

    def _get_all_site_codes(self):
        conn = self.db.connect()
        rows = conn.execute("SELECT site_code FROM sites").fetchall()
        conn.close()
        codes = [r[0] for r in rows]
        if codes:
            return codes
        return ["DFREE", "DGAN", "WBMY", "CYONG", "POLK", "SABE", "PCS"]

    def _get_sites_doc_working_root(self):
        return self.working_root / SITES_DOC_AREA

    def _get_sites_doc_archive_root(self):
        return self.archive_root / SITES_DOC_AREA

    def build_folder_paths(self, root, folder_names, stages=_NO_STAGES, doc_types=None):
        if stages is _NO_STAGES:
            stages = FOLDER_STAGES
        doc_types = doc_types or ALL_DOC_TYPES
        paths = []
        for fname in folder_names:
            if fname == SITES_DOC_AREA:
                continue
            if stages:
                for stage in stages:
                    for dt in doc_types:
                        paths.append(root / fname / stage / dt)
            else:
                for dt in doc_types:
                    paths.append(root / fname / dt)
        return paths

    def _build_sites_doc_paths(self, root, include_stages=True):
        paths = []
        sites_root = root / SITES_DOC_AREA
        if include_stages:
            paths.append(sites_root / SITES_DOC_SUBMIT)
            paths.append(sites_root / SITES_DOC_SUBMIT / "failed")
            sites = self._get_all_site_codes()
            for sc in sites:
                for ms in MILESTONES:
                    paths.append(sites_root / "Pending_Visual_Check" / sc / ms)
                    paths.append(sites_root / "Review" / sc / ms)
                    paths.append(sites_root / "Approve" / sc / ms)
        else:
            sites = self._get_all_site_codes()
            for sc in sites:
                for ms in MILESTONES:
                    paths.append(sites_root / sc / ms)
        return paths

    def ensure_folder_structure(self):
        if self.simulate:
            paths = []
            other_folders = [f for f in WORKING_FOLDERS if f != SITES_DOC_AREA]
            paths += self.build_folder_paths(self.working_root, other_folders)
            for fname in other_folders:
                submit_root = self.working_root / fname / "Submit"
                for extra in ["hot_folder", "_failed"]:
                    paths.append(submit_root / extra)
            paths += self._build_sites_doc_paths(self.working_root, include_stages=True)
            paths += self.build_folder_paths(self.archive_root, ARCHIVE_FOLDERS, stages=None)
            paths += self._build_sites_doc_paths(self.archive_root, include_stages=False)
            for p in paths:
                p.mkdir(parents=True, exist_ok=True)
            return {"status": "ok", "folders_created": len(paths)}
        else:
            return self._create_sharepoint_folders()

    def _create_sharepoint_folders(self):
        raise NotImplementedError("SharePoint API not yet connected")

    def validate_structure(self):
        expected = []
        expected += self.build_folder_paths(self.working_root, WORKING_FOLDERS)
        for fname in WORKING_FOLDERS:
            if fname == SITES_DOC_AREA:
                continue
            submit_root = self.working_root / fname / "Submit"
            for extra in ["hot_folder", "_failed"]:
                expected.append(submit_root / extra)
        expected += self._build_sites_doc_paths(self.working_root, include_stages=True)
        expected += self.build_folder_paths(self.archive_root, ARCHIVE_FOLDERS, stages=None)
        expected += self._build_sites_doc_paths(self.archive_root, include_stages=False)
        missing = [str(p) for p in expected if not p.exists()]
        return {"total_expected": len(expected), "existing": len(expected) - len(missing), "missing": missing}

    def ensure_site_folders(self, site_code):
        if not self.simulate:
            return
        for root in [self.working_root, self.archive_root]:
            area = root / SITES_DOC_AREA
            for stage in (["Pending_Visual_Check", "Review", "Approve"] if root == self.working_root else [""]):
                for ms in MILESTONES:
                    if stage:
                        p = area / stage / site_code / ms
                    else:
                        p = area / site_code / ms
                    p.mkdir(parents=True, exist_ok=True)

    def scan_review_folders(self, site_code=None):
        review_root = self._get_sites_doc_working_root() / "Review"
        if not review_root.exists():
            return []
        results = []
        for site_dir in review_root.iterdir():
            if not site_dir.is_dir():
                continue
            if site_code and site_dir.name.upper() != site_code.upper():
                continue
            sc = site_dir.name
            for ms_dir in site_dir.iterdir():
                if not ms_dir.is_dir():
                    continue
                ms = ms_dir.name
                if ms not in MILESTONES:
                    continue
                files = list(ms_dir.glob("*.pdf"))
                doc_types_found = set()
                for f in files:
                    dt = SubmitAgent._identify_doc_type(f.name)
                    if dt:
                        doc_types_found.add(dt)
                required = set(MILESTONE_DOCS.get(ms, []))
                if "TSSR" in required and "TSS" in doc_types_found:
                    doc_types_found.add("TSSR")
                if "TSS" in required and "TSSR" in doc_types_found:
                    doc_types_found.add("TSS")
                missing = sorted(required - doc_types_found)
                results.append({
                    "site_code": sc, "milestone": ms, "file_count": len(files),
                    "doc_types_found": sorted(doc_types_found),
                    "missing_docs": missing, "all_docs_present": len(missing) == 0,
                })
        return results

    def scan_pending_visual_folders(self):
        pv_root = self._get_sites_doc_working_root() / "Pending_Visual_Check"
        if not pv_root.exists():
            return []
        results = []
        for site_dir in sorted(pv_root.iterdir()):
            if not site_dir.is_dir():
                continue
            for ms_dir in sorted(site_dir.iterdir()):
                if not ms_dir.is_dir() or ms_dir.name not in MILESTONES:
                    continue
                files = list(ms_dir.glob("*.pdf"))
                if not files:
                    continue
                doc_types = []
                for f in files:
                    dt = SubmitAgent._identify_doc_type(f.name)
                    doc_types.append(dt or f.name)
                results.append({
                    "site_code": site_dir.name, "milestone": ms_dir.name,
                    "file_count": len(files), "files": [f.name for f in files], "doc_types": doc_types,
                })
        return results

    def approve_milestone(self, site_code, milestone):
        if milestone not in MILESTONES:
            return {"status": "error", "message": f"Unknown milestone: {milestone}"}
        review_dir = self._get_sites_doc_working_root() / "Review" / site_code.upper() / milestone
        approve_dir = self._get_sites_doc_working_root() / "Approve" / site_code.upper() / milestone
        if not review_dir.exists():
            return {"status": "error", "message": f"Review folder not found: {review_dir}"}
        files = list(review_dir.glob("*.pdf"))
        if not files:
            return {"status": "error", "message": "No files in review folder"}
        approve_dir.mkdir(parents=True, exist_ok=True)
        moved = []
        for f in files:
            shutil.move(str(f), str(approve_dir / f.name))
            moved.append(f.name)
        remaining = list(review_dir.glob("*"))
        if not remaining:
            review_dir.rmdir()
        return {"status": "ok", "site_code": site_code, "milestone": milestone, "files_moved": moved}

    def get_approval_ready_list(self):
        reviews = self.scan_review_folders()
        return [r for r in reviews if r["all_docs_present"] and r["file_count"] > 0]

    def get_archive_ready_list(self):
        approve_root = self._get_sites_doc_working_root() / "Approve"
        if not approve_root.exists():
            return []
        results = []
        for site_dir in approve_root.iterdir():
            if not site_dir.is_dir():
                continue
            for ms_dir in site_dir.iterdir():
                if not ms_dir.is_dir() or ms_dir.name not in MILESTONES:
                    continue
                files = list(ms_dir.glob("*.pdf"))
                if files:
                    results.append({
                        "site_code": site_dir.name, "milestone": ms_dir.name, "file_count": len(files),
                    })
        return results

    def run_archive_cycle(self):
        ready = self.get_archive_ready_list()
        archived = 0
        for r in ready:
            src = self._get_sites_doc_working_root() / "Approve" / r["site_code"] / r["milestone"]
            dst = self._get_sites_doc_archive_root() / r["site_code"] / r["milestone"]
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.pdf"):
                shutil.move(str(f), str(dst / f.name))
                archived += 1
            remaining = list(src.glob("*"))
            if not remaining:
                src.rmdir()
        return {"status": "ok", "archived": archived}

    def watch_archive(self):
        import time
        print(f"Watching for approval changes every {WATCH_INTERVAL_SECONDS}s...")
        while True:
            result = self.run_archive_cycle()
            if result["archived"]:
                print(f"{datetime.now()}: Archived {result['archived']} file(s)")
            time.sleep(WATCH_INTERVAL_SECONDS)

    def delta_query(self, site_code=None):
        results = []
        for stage in ["Pending_Visual_Check", "Review", "Approve"]:
            root = self._get_sites_doc_working_root() / stage
            if not root.exists():
                continue
            for site_dir in root.iterdir():
                if not site_dir.is_dir():
                    continue
                if site_code and site_dir.name.upper() != site_code.upper():
                    continue
                for ms_dir in site_dir.iterdir():
                    if not ms_dir.is_dir() or ms_dir.name not in MILESTONES:
                        continue
                    for f in ms_dir.glob("*.pdf"):
                        results.append({
                            "site_code": site_dir.name, "milestone": ms_dir.name,
                            "stage": stage, "filename": f.name,
                            "size_kb": round(f.stat().st_size / 1024, 1),
                            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                        })
        return results


class SubmitAgent:
    """Handles document submission pipeline: hot folder → quality check → Review."""

    def __init__(self, db=None, simulate=True):
        self.db = db or DatabaseAgent()
        self.simulate = simulate
        sites_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA
        sim_root = sites_root / SITES_DOC_SUBMIT
        self.hot_folder = sim_root
        self.failed_folder = sim_root / "failed"
        self.pending_visual_root = sites_root / "Pending_Visual_Check"

        if simulate:
            self.hot_folder.mkdir(parents=True, exist_ok=True)
            self.failed_folder.mkdir(parents=True, exist_ok=True)
            self.pending_visual_root.mkdir(parents=True, exist_ok=True)

        self.default_rules = [self._rule_pdf_valid, self._rule_has_text, self._rule_file_naming]
        self.quality_rules = {
            "TSSR": [self._rule_tssr_content, partial(self._rule_no_blurry_pages, threshold=300, resize_width=500), self._rule_min_photos_per_category, self._rule_has_signature],
            "SATP": [self._rule_satp_content, partial(self._rule_no_blurry_pages, threshold=300, resize_width=500), self._rule_has_signature],
            "PL": [self._rule_pl_content, partial(self._rule_has_signature, last_page_only=True)],
            "PO": [self._rule_po_content, self._rule_has_signature],
            "DN": [self._rule_dn_content, partial(self._rule_has_signature, last_page_only=True)],
            "BL": [self._rule_bl_content],
            "MOP": [self._rule_mop_content, self._rule_has_signature],
            "SMR": [self._rule_smr_content, partial(self._rule_has_signature, start_page=2, end_page=2)],
            "CC": [self._rule_cc_content, partial(self._rule_has_signature, last_page_only=True)],
            "FT": [self._rule_ft_content, partial(self._rule_no_blurry_pages, threshold=1000), partial(self._rule_has_signature, start_page=6)],
            "PAF": [self._rule_paf_content, partial(self._rule_has_signature, last_page_only=True)],
            "FAF": [self._rule_faf_content, partial(self._rule_has_signature, last_page_only=True)],
        }

    @staticmethod
    def _identify_doc_type(filename):
        stem = Path(filename).stem
        parts = stem.split("_")
        if parts:
            dt = parts[0].upper()
            valid_types = ["PO", "DN", "BL", "PL", "TSSR", "SATP", "MOP", "SMR", "CC", "FT", "PAF", "FAF"]
            renames = {"BOL": "BL", "TSS": "TSSR", "PAC": "PAF"}
            if dt in valid_types:
                return dt
            if dt in renames:
                return renames[dt]
        return None

    def _parse_filename(self, filename):
        from agents.extract_base import _parse_filename
        return _parse_filename(filename)

    def _get_review_milestone_dir(self, site_code, milestone):
        sites_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA
        return sites_root / "Review" / site_code.upper() / milestone

    def _extract_text(self, pdf_path):
        """Extract text from PDF, with OCR fallback for scanned docs."""
        import fitz
        doc = fitz.open(str(pdf_path))
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        if len(text.strip()) < 50:
            text = self._ocr_fallback(pdf_path)
        return text

    def _ocr_fallback(self, pdf_path):
        """OCR fallback using pytesseract at 200dpi (per v5 matrix)."""
        import fitz, pytesseract
        from PIL import Image
        import io
        doc = fitz.open(str(pdf_path))
        texts = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            img_pil = Image.open(io.BytesIO(img_bytes))
            t = pytesseract.image_to_string(img_pil, config="--psm 6")
            texts.append(t)
        doc.close()
        return " ".join(texts)

    def verify_document(self, pdf_path):
        """Run quality verification rules on a document. Returns list of results."""
        import fitz
        pdf_path = Path(pdf_path)
        filename = pdf_path.name
        doc_type = self._identify_doc_type(filename)
        if not doc_type:
            return {"passed": False, "status": "failed", "issues": ["Unknown document type"], "doc_type": None, "page_count": 0, "results": [{"rule": "doc_type", "passed": False, "message": "Unknown document type"}]}

        try:
            doc = fitz.open(str(pdf_path))
            page_count = doc.page_count
            doc.close()
        except Exception as e:
            return {"passed": False, "status": "failed", "issues": [f"Invalid PDF: {e}"], "doc_type": doc_type, "page_count": 0, "results": [{"rule": "pdf_valid", "passed": False, "message": f"Invalid PDF: {e}"}]}

        # Extract text once
        text = self._extract_text(pdf_path)

        rules = self.default_rules + self.quality_rules.get(doc_type, [])
        results = []
        for rule in rules:
            rule_name = getattr(rule, "__name__", str(rule))
            try:
                result = rule(pdf_path, text=text, doc_type=doc_type)
                if isinstance(result, dict):
                    result["rule"] = rule_name
                    results.append(result)
                elif isinstance(result, bool):
                    results.append({"rule": rule_name, "passed": result, "message": ""})
                else:
                    results.append({"rule": rule_name, "passed": True, "message": ""})
            except Exception as e:
                results.append({"rule": rule_name, "passed": False, "message": str(e)})

        # Determine overall pass/fail
        all_passed = all(r.get("passed", False) for r in results)
        needs_review = any(r.get("manual_review") for r in results)
        ret = {
            "passed": all_passed,
            "status": "passed" if all_passed else "failed",
            "results": results,
            "doc_type": doc_type,
            "page_count": page_count,
            "issues": [r["message"] for r in results if not r.get("passed")],
        }
        if needs_review:
            ret["manual_review"] = True
        return ret

    # ── Quality Rules ──

    def _rule_pdf_valid(self, pdf_path, **kw):
        import fitz
        try:
            doc = fitz.open(str(pdf_path))
            count = doc.page_count
            doc.close()
            if count == 0:
                return {"passed": False, "message": "PDF has 0 pages"}
            return {"passed": True, "message": f"Valid PDF ({count} pages)"}
        except Exception as e:
            return {"passed": False, "message": f"Invalid PDF: {e}"}

    def _rule_file_naming(self, pdf_path, **kw):
        import re
        name = Path(pdf_path).name
        if re.match(r'^[A-Za-z0-9\s]+_[A-Za-z0-9]+_[A-Za-z\s]+_\d{8}\.pdf$', name):
            return {"passed": True, "message": f"Filename matches convention: {name}"}
        return {"passed": False, "message": f"Filename does not match convention: {name}"}

    def _rule_has_text(self, pdf_path, text="", **kw):
        if len(text.strip()) >= 10:
            return {"passed": True, "message": f"Text extracted ({len(text.strip())} chars)"}
        return {"passed": False, "message": "Document has insufficient text (< 10 chars after OCR)"}

    def _rule_has_signature(self, pdf_path, text="", last_page_only=False, start_page=None, end_page=None, **kw):
        import fitz, cv2, numpy as np
        from agents.handwriting_ocr import has_signature_zone
        doc = fitz.open(str(pdf_path))
        total = doc.page_count

        # Fast path: if extracted text has signature keywords, skip per-page OCR
        if len(text.strip()) >= 50:
            upper = text.upper()
            sig_kw = ["SIGNATURE", "SIGNED", "AUTHORIZED BY", "APPROVED BY", "PREPARED BY", "DATE:", "ANAK", "BIN ", "BINTI"]
            if any(kw in upper for kw in sig_kw):
                doc.close()
                return {"passed": True, "message": "Signature keywords found in document text"}

        # Determine which pages to scan
        if last_page_only:
            page_range = [doc[-1]]
        elif start_page is not None or end_page is not None:
            p_start = (start_page or 1) - 1
            p_end = min((end_page or total) - 1, total - 1)
            page_range = [doc[i] for i in range(p_start, p_end + 1)]
        else:
            page_range = list(doc)

        all_pages_data = []  # Collect all detections with scores

        for page in page_range:
            page_text = page.get_text().upper()
            page_num = page.number + 1
            page_data = {"page": page_num, "detections": [], "score": 0}

            # 1. Text label detection (highest weight)
            for kw_label in ["SIGNATURE", "SIGNED", "AUTHORIZED BY", "APPROVED BY", "PREPARED BY", "DATE:"]:
                if kw_label in page_text:
                    page_data["detections"].append({"type": "text_label", "label": kw_label})
                    page_data["score"] += 10

            # 2. Image-based: embedded signature stamp images
            images = page.get_images(full=True)
            for img_info in images:
                xref = img_info[0]
                try:
                    bbox = page.get_image_bbox(xref)
                except ValueError:
                    continue
                w = bbox.width
                h = bbox.height
                aspect = w / h if h > 0 else 0
                if 30 <= w <= 200 and 15 <= h <= 100 and aspect > 1.2:
                    text_blocks = page.get_text("blocks")
                    na_nearby = any(
                        abs(block[1] - bbox.y0) < 50 and "N/A" in block[4].upper()
                        for block in text_blocks
                    )
                    if not na_nearby:
                        page_data["detections"].append({"type": "image", "bbox": [bbox.x0, bbox.y0, bbox.x1, bbox.y1]})
                        page_data["score"] += 5

            if page_data["detections"]:
                all_pages_data.append(page_data)
                continue  # Skip OCR for pages already matched by text/image

            # 3. OCR-based: render and check via EasyOCR + contour
            pix = page.get_pixmap(dpi=150)
            img_data = pix.tobytes("png")
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(img_data)
                tmp_path = tmp.name
            img_cv = cv2.imread(tmp_path)
            os.unlink(tmp_path)
            if img_cv is not None:
                sig_result = has_signature_zone(img_cv)
                if sig_result.get("has_signature"):
                    for loc in sig_result.get("locations", []):
                        page_data["detections"].append({"type": "ocr", **loc})
                        page_data["score"] += float(loc.get("area", 0)) / 1000 + 2
                    if page_data["detections"]:
                        all_pages_data.append(page_data)

        doc.close()

        if all_pages_data:
            # Sort by score descending — pick highest-scored page as primary
            all_pages_data.sort(key=lambda p: p["score"], reverse=True)
            locs = []
            for pd in all_pages_data:
                for d in pd["detections"]:
                    b = d.get("bbox", "")
                    label = d.get("label", d.get("type", ""))
                    locs.append(f"Page {pd['page']}: {label} @ {b}")
            sig_msg = "; ".join(locs)
            return {
                "passed": True,
                "message": f"Signature detected: {sig_msg}",
                "signature_pages": all_pages_data,
            }

        return {"passed": True, "manual_review": True, "message": "Signature zone not detected by OCR — manual review required"}

    def _rule_no_blurry_pages(self, pdf_path, threshold=1000, resize_width=None, **kw):
        import fitz, cv2, numpy as np
        doc = fitz.open(str(pdf_path))
        blurry = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=100)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            if resize_width:
                scale = resize_width / gray.shape[1]
                gray = cv2.resize(gray, (resize_width, int(gray.shape[0] * scale)))
            mean_gray = gray.mean()
            if mean_gray > 245:
                continue  # skip blank pages
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()
            if variance < threshold:
                blurry.append(i + 1)
        doc.close()
        if blurry:
            return {"passed": False, "message": f"Blurry pages: {blurry} (variance < {threshold})"}
        return {"passed": True, "message": "No blurry pages"}

    def _rule_min_photos_per_category(self, pdf_path, **kw):
        import fitz, cv2, numpy as np
        doc = fitz.open(str(pdf_path))
        categories = {}
        current_cat = "Uncategorized"
        for i, page in enumerate(doc):
            if i == 0:
                continue
            text = page.get_text().strip()
            lines = text.split("\n")
            heading = None
            for line in lines[:5]:
                if re.match(r"^\d+\.\d+", line.strip()):
                    heading = line.strip()
                    break
            if heading:
                current_cat = heading
            pix = page.get_pixmap(dpi=100)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            h, w = gray.shape
            if h >= 200 and w >= 200:
                cat_list = categories.setdefault(current_cat, [])
                cat_list.append(i + 1)
        doc.close()
        issues = []
        for cat, pages in categories.items():
            if len(pages) == 0:
                issues.append(f"Category '{cat}' has 0 photos")
        if issues:
            return {"passed": False, "message": "; ".join(issues)}
        return {"passed": True, "message": f"{sum(len(v) for v in categories.values())} photos across {len(categories)} categories"}

    def _rule_tssr_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        manual_review = False

        # Required fields — OR-style with OCR-tolerant regex
        if re.search(r'SITE\s*NAME', upper) or "SITENAME" in upper:
            checks.append("SITE NAME")
        else:
            manual_review = True
        if re.search(r'SITE\s*OWNER', upper) or "SITEOWNER" in upper:
            checks.append("SITE OWNER")
        if re.search(r'TOWER\s*ID', upper) or "TOWERID" in upper:
            checks.append("TOWER ID")
        if "REGION" in upper:
            checks.append("REGION")
        if re.search(r'SITE\s*STRUCTURE', upper) or "SITESTRUCTURE" in upper:
            checks.append("SITE STRUCTURE")
        if re.search(r'EQUIPMENT\s*MODEL', upper) or "EQUIPMENTMODEL" in upper:
            checks.append("EQUIPMENT MODEL")
        if re.search(r'EQUIPMENT\s*FUNCTION', upper) or "EQUIPMENTFUNCTION" in upper:
            checks.append("EQUIPMENT FUNCTION")
        if "LATITUDE" in upper or "LATITUDE/LONGITUDE" in upper or "LAT/LONG" in upper:
            checks.append("LAT/LNG label")

        # NMS LRD match against filename — substring tolerant
        name = Path(pdf_path).name
        parsed = self._parse_filename(name)
        if parsed:
            filename_site = parsed[1]
            nms_lrd = ""
            idx = upper.find("NMS LRD")
            if idx == -1:
                idx = upper.find("CONTRACT NO")
            if idx >= 0:
                snippet = upper[idx:idx+150]
                m = re.search(r'(?:NMS\s*LRD|CONTRACT\s*NO)\s*[:.]?\s*([A-Z0-9]+)', snippet)
                if m:
                    nms_lrd = m.group(1)
            if nms_lrd and filename_site:
                if nms_lrd == filename_site.upper() or nms_lrd.startswith(filename_site.upper()) or filename_site.upper() in nms_lrd:
                    checks.append(f"NMS LRD matches ({nms_lrd})")
                else:
                    manual_review = True
                    checks.append(f"NMS LRD '{nms_lrd}' ≈ '{filename_site}' (OCR mismatch)")
            elif nms_lrd:
                checks.append(f"NMS LRD ({nms_lrd})")

        msg = "TSSR content: " + ", ".join(checks) if checks else "TSSR content check skipped (limited text)"
        if manual_review:
            return {"passed": True, "manual_review": True, "message": msg + " — some fields not confirmed by OCR, manual review required"}
        return {"passed": True, "message": msg}

    def _rule_satp_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        manual_review = False

        # Required fields with OCR-tolerant variants
        if re.search(r'SITE\s*NAME', upper) or "SITENAME" in upper:
            checks.append("SITE NAME")
        else:
            manual_review = True
        if re.search(r'SITE\s*OWNER', upper) or "SITEOWNER" in upper:
            checks.append("SITE OWNER")
        if re.search(r'NMS\s*LRD', upper) or re.search(r'LRD\s*:', upper):
            checks.append("NMS LRD")
        if "LAT/LONG" in upper or ("LATITUDE" in upper and "LONGITUDE" in upper) or "LATITUDE/LONGITUDE" in upper:
            checks.append("LAT/LONG")

        # Heading check
        if re.search(r'SITE\s*ACCEPTANCE\s*TEST\s*PROCEDURE', upper) or "SATP INFO" in upper:
            checks.append("SATP heading")

        # Signing page — lax: any of these is enough
        if re.search(r'PREPARED\s*BY', upper) or re.search(r'SURVEYOR\s*NAME', upper):
            checks.append("Prepared By/Surveyor")
        if re.search(r'VERIFIED\s*BY', upper):
            checks.append("Verified By")
        if re.search(r'\b\d{2}[/-]\d{2}[/-]\d{4}\b', text):
            checks.append("date")

        msg = f"SATP content: {', '.join(checks)}" if checks else "SATP content check skipped (limited text)"
        if manual_review:
            return {"passed": True, "manual_review": True, "message": msg + " — SITE NAME not detected by OCR, manual review required"}
        return {"passed": True, "message": msg}

    def _rule_po_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "PURCHASE ORDER" in upper or re.search(r'PO\s*(NO|#|NUMBER)', upper):
            checks.append("PO heading/number")
        if "VENDOR" in upper or "SUPPLIER" in upper or "ORDER TO" in upper:
            checks.append("vendor/supplier")
        if re.search(r'\b\d{2}/\d{2}/\d{4}\b', text):
            checks.append("date (dd/mm/yyyy)")
        if checks:
            return {"passed": True, "message": f"PO content: {', '.join(checks)}"}
        return {"passed": True, "message": "PO content check skipped (limited text)"}

    def _rule_dn_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "DELIVERY NOTE" in upper or "DELIVERY ORDER" in upper or re.search(r'DN\s*(NO|#|NUMBER)', upper) or re.search(r'DO\s*(NO|#|NUMBER)', upper):
            checks.append("DN/DO heading")
        if "CUSTOMER" in upper or "CONSIGNEE" in upper or "SACOFA" in upper or "IX TELECOM" in upper:
            checks.append("customer/consignee")
        if re.search(r'\b\d{2}/\d{2}/\d{4}\b|\b\d{8}\b', text):
            checks.append("date")
        if checks:
            return {"passed": True, "message": f"DN content: {', '.join(checks)}"}
        return {"passed": True, "message": "DN content check skipped"}

    def _rule_pl_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "PACKING LIST" in upper:
            checks.append("Packing List heading")
        if re.search(r'(?:PR|SOR)\s*/\s*\d{4}\s*/\s*\d{4}', upper) or re.search(r'SSB\s*/\s*PO\s*/\s*\d{4}', upper):
            checks.append("reference/PO number")
        if "CONSIGNEE" in upper or "PROJECT" in upper:
            checks.append("consignee/project")
        if "PREPARED BY" in upper:
            checks.append("Prepared By")
        if re.search(r'TOTAL\s*(QTY|QUANTITY)', upper):
            checks.append("Total Quantity")
        if checks:
            return {"passed": True, "message": f"PL content: {', '.join(checks)}"}
        return {"passed": True, "message": "PL content check skipped"}

    def _rule_bl_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "BILL OF LADING" in upper or "BILL OF LANDING" in upper:
            checks.append("BL heading")
        if re.search(r'(?:CONTAINER|BL)\s*(?:NO|#|NUMBER)?[:.]?\s*\w+', upper):
            checks.append("container/BL number")
        if "SHIPPER" in upper and "ZTE" in upper:
            checks.append("shipper (ZTE)")
        if "CONSIGNEE" in upper and "MALAYSIA" in upper:
            checks.append("consignee (ZTE Malaysia)")
        port_labels = ["PORT OF LOADING", "PORT OF DISCHARGE", "LOADING", "DISCHARGE"]
        if any(p in upper for p in port_labels):
            checks.append("port information")
        if "VESSEL" in upper or "VOYAGE" in upper:
            checks.append("vessel/voyage")
        if checks:
            return {"passed": True, "message": f"BL content: {', '.join(checks)}"}
        return {"passed": True, "message": "BL content check skipped"}

    def _rule_mop_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "METHOD OF PROCEDURE" in upper:
            checks.append("MOP heading")
        if re.search(r'(?:VERSION|REVISION|REV)\s*[:.]?\s*\d+', upper):
            checks.append("version/revision")
        if re.search(r'\b\d{2}/\d{2}/\d{4}\b', text):
            checks.append("date")
        if "PREPARED BY" in upper or "VERIFIED BY" in upper or "APPROVED BY" in upper:
            checks.append("signatory labels")
        if checks:
            return {"passed": True, "message": f"MOP content: {', '.join(checks)}"}
        return {"passed": True, "message": "MOP content check skipped"}

    def _rule_smr_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "SERVICE MIGRATION REPORT" in upper or "SITE MIGRATION REPORT" in upper:
            checks.append("SMR heading")
        required_fields = ["SITE NAME", "SITE OWNER", "LATITUDE", "LONGITUDE", "REGION", "SITE STRUCTURE", "EQUIPMENT MODEL", "EQUIPMENT FUNCTION"]
        found_fields = [f for f in required_fields if f in upper]
        if found_fields:
            checks.append(f"fields: {len(found_fields)}/{len(required_fields)}")
        if re.search(r'(?:PREPARED BY|VERIFIED BY|APPROVED BY)', upper):
            checks.append("signatory blocks")
        if checks:
            return {"passed": True, "message": f"SMR content: {', '.join(checks)}"}
        return {"passed": True, "message": "SMR content check skipped"}

    def _rule_cc_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "COMMISSIONING" in upper or "COMPLETION CERTIFICATE" in upper:
            checks.append("CC heading")
        if "NMS LRD" in upper:
            checks.append("NMS LRD present")
        if "CERTIFIED BY" in upper or "APPROVED BY" in upper or "ACCEPTANCE" in upper:
            checks.append("acceptance/signatory zone")
        if re.search(r'\b\d{2}/\d{2}/\d{4}\b', text):
            checks.append("date")
        if checks:
            return {"passed": True, "message": f"CC content: {', '.join(checks)}"}
        return {"passed": True, "message": "CC content check skipped"}

    def _rule_ft_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "FUNCTIONALITY TEST" in upper or "FUNCTIONAL TEST" in upper:
            checks.append("FT heading")
        if "NODE NAME" in upper or "NODE" in upper:
            checks.append("Node Name")
        if re.search(r'\b\d{2}/\d{2}/\d{4}\b', text):
            checks.append("date")
        if "TESTED BY" in upper or "PREPARED BY" in upper:
            checks.append("signatory label")
        if checks:
            return {"passed": True, "message": f"FT content: {', '.join(checks)}"}
        return {"passed": True, "message": "FT content check skipped"}

    def _rule_paf_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "PROVISIONAL ACCEPTANCE" in upper or "PRELIMINARY ACCEPTANCE" in upper or "PAC APPROVAL" in upper:
            checks.append("PAF heading")
        if "NMS LRD" in upper:
            checks.append("NMS LRD present")
        if "ACCEPTANCE" in upper or "CERTIFIED BY" in upper or "APPROVED BY" in upper:
            checks.append("acceptance/signatory zone")
        if re.search(r'\b\d{2}/\d{2}/\d{4}\b', text):
            checks.append("date")
        if checks:
            return {"passed": True, "message": f"PAF content: {', '.join(checks)}"}
        return {"passed": True, "message": "PAF content check skipped"}

    def _rule_faf_content(self, pdf_path, text="", **kw):
        if not text:
            return {"passed": True, "message": "OCR text not available, skipping"}
        upper = text.upper()
        checks = []
        if "FINAL ACCEPTANCE" in upper or "FAC ACCEPTANCE" in upper:
            checks.append("FAF heading")
        if "NMS LRD" in upper:
            checks.append("NMS LRD present")
        if "ACCEPTANCE" in upper or "CERTIFIED BY" in upper or "APPROVED BY" in upper:
            checks.append("acceptance/signatory zone")
        if re.search(r'\b\d{2}/\d{2}/\d{4}\b', text):
            checks.append("date")
        if checks:
            return {"passed": True, "message": f"FAF content: {', '.join(checks)}"}
        return {"passed": True, "message": "FAF content check skipped"}
        upper = text.upper()
        if "FAC ACCEPTANCE" in upper or "FINAL ACCEPTANCE" in upper:
            return {"passed": True, "message": "FAF heading found"}
        return {"passed": True, "message": "FAF content check skipped"}

    # ── Cross-Document Validation ──

    def cross_check_cc_docs(self, site_code):
        """Cross-validate CC milestone docs for a site: site label per doc type, PO#, ref, contract."""
        review_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Review" / site_code.upper() / "CC"
        if not review_root.exists():
            return {"passed": False, "status": "fail", "issues": ["Review folder not found"], "details": {}}

        docs = {}
        for f in review_root.glob("*.pdf"):
            dt = self._identify_doc_type(f.name)
            if dt:
                docs[dt] = f

        required = ["PO", "DN", "BL", "PL", "SATP"]
        missing = [d for d in required if d not in docs]
        if missing:
            return {"passed": False, "status": "fail", "issues": [f"Missing docs: {missing}"], "details": {}}

        texts = {}
        ocr_docs = []
        for dt, fp in docs.items():
            t = self._extract_text(fp)
            texts[dt] = t
            if len(t.strip()) < 50:
                ocr_docs.append(dt)

        details = {}
        issues = []
        upper_sc = site_code.upper()
        sc_escaped = re.escape(upper_sc)

        # ── Site label per doc type (BL exempted) ──
        site_label_checks = {
            "TSSR": {
                "label": "NMS LRD",
                "check": lambda t: re.search(rf'NMS\s*LRD[^A-Z]*{sc_escaped}', t, re.IGNORECASE)
            },
            "SATP": {
                "label": "NMS LRD",
                "check": lambda t: re.search(rf'NMS\s*LRD[^A-Z]*{sc_escaped}', t, re.IGNORECASE)
            },
            "PO": {
                "label": "SACOFA LRD (Remark box last page)",
                "check": lambda t: re.search(rf'SACOFA\s*LRD[^A-Z]*{sc_escaped}', t, re.IGNORECASE) or re.search(rf'LRD[^A-Z]*{sc_escaped}', t, re.IGNORECASE)
            },
            "PL": {
                "label": "Site:",
                "check": lambda t: re.search(rf'SITE\s*:\s*{sc_escaped}', t, re.IGNORECASE)
            },
            "FT": {
                "label": "Node Name (XX.[SITE]-[NODE]-xx-xxxx)",
                "check": lambda t: re.search(rf'\d+\s*\.\s*\[?\s*{sc_escaped}\s*\]?\s*\-', t, re.IGNORECASE)
            },
            "DN": {
                "label": "Site ID",
                "check": lambda t: re.search(rf'SITE\s*ID[^A-Z]*{sc_escaped}', t, re.IGNORECASE)
            },
        }

        for dt, rule in site_label_checks.items():
            doc_text = texts.get(dt, "")
            if not doc_text.strip():
                continue  # OCR content unavailable, will be caught by ocr_docs
            match = rule["check"](doc_text)
            details[f"{dt}_site_label"] = f"{rule['label']} {'FOUND' if match else 'NOT FOUND'}"
            if not match:
                issues.append(f"{dt}: {rule['label']} not found in document")

        # PO# exact match PO <-> PL
        po_text = texts.get("PO", "")
        pl_text = texts.get("PL", "")
        po_match = re.search(r'(?:PO\s*(?:NO|#|NUMBER)?[:.]?\s*)(\S+)', po_text, re.IGNORECASE)
        po_number = po_match.group(1).strip().rstrip(".,:;") if po_match else ""
        details["po_number"] = po_number or "NOT FOUND"

        if po_number:
            if re.search(rf'\b{re.escape(po_number)}\b', pl_text):
                details["PL_has_exact_po_number"] = True
            else:
                if po_number in pl_text:
                    details["PL_has_exact_po_number"] = "partial"
                else:
                    details["PL_has_exact_po_number"] = False
                    issues.append(f"PO# {po_number} not found in PL")

        # PO Reference No in PL
        po_ref = re.search(r'(?:REF(?:ERENCE)?\s*(?:NO|#|NUMBER)?[:.]?\s*)(\S+)', po_text, re.IGNORECASE)
        po_ref_no = po_ref.group(1).strip().rstrip(".,:;") if po_ref else ""
        details["po_ref_number"] = po_ref_no or "NOT FOUND"
        if po_ref_no and len(po_ref_no) > 5:
            if po_ref_no in pl_text:
                details["PL_has_ref_number"] = True
            else:
                details["PL_has_ref_number"] = False
                issues.append(f"Reference No {po_ref_no} from PO not found in PL")

        # Contract No from DN traceable in BL
        dn_text = texts.get("DN", "")
        bl_text = texts.get("BL", "")
        contract_match = re.search(r'(?:CONTRACT\s*(?:NO|#|NUMBER)?[:.]?\s*)(\S+)', dn_text, re.IGNORECASE)
        contract_no = contract_match.group(1).strip().rstrip(".,:;") if contract_match else ""
        details["dn_contract_no"] = contract_no or "NOT FOUND"
        if contract_no and len(contract_no) > 5:
            if contract_no in bl_text:
                details["BL_has_dn_contract_no"] = True
            else:
                for part in [contract_no[:15], contract_no[:10]]:
                    if part in bl_text:
                        details["BL_has_dn_contract_no"] = f"partial ({part})"
                        break
                else:
                    details["BL_has_dn_contract_no"] = False
                    issues.append(f"Contract No {contract_no} from DN not found in BL")

        details["ocr_docs"] = ocr_docs
        details["ocr_note"] = "OCR used — results may be unreliable, PMC visual confirmation required"

        if ocr_docs:
            return {"passed": True, "status": "undetermined", "issues": [], "details": details, "ocr_required": True}
        if issues:
            return {"passed": False, "status": "fail", "issues": issues, "details": details, "ocr_required": False}

        return {"passed": True, "status": "pass", "issues": [], "details": details, "ocr_required": False}

    # ── Pipeline Processing ──

    def _auto_rename(self, pdf_path):
        """Rename file to convention [DOCTYPE]_[SITENAME]_[NODETYPE]_[YYYYMMDD].pdf if possible."""
        import shutil, re
        from datetime import datetime
        pdf_path = Path(pdf_path)
        name = pdf_path.name
        parsed = self._parse_filename(name)
        if parsed and parsed[0]:
            # Verify the parsed doc type is actually valid before skipping
            valid_types_inner = ["PO", "DN", "BL", "PL", "TSSR", "SATP", "MOP", "SMR", "CC", "FT", "PAF", "FAF"]
            type_map_inner = {"BOL": "BL", "TSS": "TSSR", "PAC": "PAF"}
            if parsed[0].upper() in valid_types_inner or parsed[0].upper() in type_map_inner:
                return pdf_path  # already valid
            # Malformed — parsed[0] is not a real doc type, proceed with rename logic

        today_str = datetime.now().strftime("%Y%m%d")
        stem = pdf_path.stem
        parts = stem.split("_")
        valid_types = ["PO", "DN", "BL", "PL", "TSSR", "SATP", "MOP", "SMR", "CC", "FT", "PAF", "FAF"]
        # Map old PAC doc type to PAF (v5 matrix)
        type_map = {"PAC": "PAF", "TSS": "TSSR", "BOL": "BL"}

        # Try sitename-first format: NODETYPE_SITE_DOCTYPE.pdf  (e.g. ACC_APONG_BL.pdf)
        if len(parts) >= 3:
            last = parts[-1].upper()
            mid = parts[-2].upper()
            raw_type = last if last in valid_types or last in type_map else None
            if raw_type or last in ("TSS", "BOL"):
                dt = type_map.get(last, last)
                site = mid
                nodetype = "_".join(parts[:-2])
                date_str = ""
                for p in parts:
                    m = re.search(r'(\d{8})', p)
                    if m:
                        date_str = m.group(1)
                        break
                if not date_str:
                    date_str = today_str
                new_name = f"{dt}_{site}_{nodetype}_{date_str}.pdf"
                new_path = pdf_path.parent / new_name
                if not new_path.exists():
                    shutil.move(str(pdf_path), str(new_path))
                    return new_path
                return pdf_path

        # Fallback: try to identify doc type from first token
        dt = self._identify_doc_type(name)
        if not dt and parts:
            candidate = parts[0].upper()
            if candidate in valid_types:
                dt = candidate
            elif candidate in type_map:
                dt = type_map[candidate]
        if not dt:
            return pdf_path
        date_match = re.search(r'(\d{8})', stem)
        date_str = date_match.group(1) if date_match else today_str
        site = parts[1] if len(parts) > 1 else "UNKNOWN"
        nodetype = parts[2] if len(parts) > 2 else "NODE"
        new_name = f"{dt}_{site}_{nodetype}_{date_str}.pdf"
        new_path = pdf_path.parent / new_name
        if new_path.exists():
            return pdf_path
        shutil.move(str(pdf_path), str(new_path))
        return new_path

    def _expand_multi_node(self, pdf_path):
        """Expand multi-node filenames where any segment contains &.
        Handles both prefix form (RNC&TRUNK_SITE_DOCTYPE_DATE.pdf)
        and node-type position (DOCTYPE_SITE_RNC&TRUNK_DATE.pdf).
        Creates single-node copies and returns list of Paths."""
        import shutil
        pdf_path = Path(pdf_path)
        stem = pdf_path.stem
        parts = stem.split("_")
        # Find the segment containing &
        amp_idx = None
        for i, p in enumerate(parts):
            if "&" in p:
                amp_idx = i
                break
        if amp_idx is None:
            return [pdf_path]
        node_types = parts[amp_idx].upper().split("&")
        suffix = pdf_path.suffix
        new_paths = []
        for nt in node_types:
            new_parts = list(parts)
            new_parts[amp_idx] = nt
            new_name = "_".join(new_parts) + suffix
            new_path = pdf_path.parent / new_name
            if not new_path.exists():
                shutil.copy2(str(pdf_path), str(new_path))
            new_paths.append(new_path)
        pdf_path.unlink(missing_ok=True)
        return new_paths

    def process_file(self, pdf_path, auto_rename=True):
        """Process a single PDF through the pipeline: extract → verify → route."""
        import fitz, shutil
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {"file": pdf_path.name, "status": "skipped", "reason": "File not found after rename"}

        # Expand multi-node filenames (RNC&TRUNK → RNC + TRUNK copies)
        expanded = self._expand_multi_node(pdf_path)
        if len(expanded) > 1:
            results = []
            for p in expanded:
                results.append(self.process_file(p, auto_rename=auto_rename))
            return {
                "file": pdf_path.name,
                "status": "multi_node",
                "children": results,
            }

        if auto_rename:
            pdf_path = self._auto_rename(pdf_path)

        if not pdf_path.exists():
            return {"file": pdf_path.name, "status": "skipped", "reason": "File not found after rename"}

        filename = pdf_path.name

        # Identify doc type from filename
        doc_type = self._identify_doc_type(filename)
        if not doc_type:
            dest = self.failed_folder / filename
            shutil.move(str(pdf_path), str(dest))
            return {"file": filename, "status": "rejected", "issues": ["Unknown document type"]}

        # Extract site_code from filename
        parsed = self._parse_filename(filename)
        site_code = parsed[1] if parsed and parsed[1] else "UNKNOWN"
        site_code = site_code.upper()

        # Determine milestones
        milestones = []
        for ms, docs in MILESTONE_DOCS.items():
            if doc_type in docs or doc_type in ("TSS", "BOL") and ("TSSR" in docs or "BL" in docs):
                milestones.append(ms)
        if not milestones:
            dest = self.failed_folder / filename
            shutil.move(str(pdf_path), str(dest))
            return {"file": filename, "status": "rejected", "issues": [f"No milestone for doc type {doc_type}"]}

        # Verify quality
        verify_result = self.verify_document(pdf_path)
        # Store verification result in DB
        try:
            from datetime import datetime
            verified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            vstatus = verify_result.get("status", "unknown")
            if verify_result.get("manual_review"):
                vstatus = "manual_review"
            self.db.upsert_verification(doc_type, {
                "sitename": site_code,
                "status": vstatus,
                "issues": "; ".join(verify_result.get("issues", [])),
                "verified_at": verified_at,
            })
        except Exception:
            pass
        if not verify_result.get("passed", False):
            dest = self.failed_folder / filename
            shutil.move(str(pdf_path), str(dest))
            return {
                "file": filename, "doc_type": doc_type, "site_code": site_code,
                "milestones": milestones, "status": "rejected", "dests": [],
                "issues": verify_result.get("issues", ["Quality check failed"]),
            }

        # Manual review needed (e.g. SATP where OCR couldn't read SITE NAME)
        if verify_result.get("manual_review"):
            pending_dir = self.pending_visual_root / site_code
            pending_dir.mkdir(parents=True, exist_ok=True)
            pending_dest = pending_dir / filename
            issues = verify_result.get("issues", ["Manual review required"])
            with open(str(pending_dest) + ".issues", "w") as f:
                json.dump({"issues": issues, "source": "quality_check"}, f)
            shutil.move(str(pdf_path), str(pending_dest))
            for m in milestones:
                try:
                    self.db.upsert_document(site_code, doc_type, filename, milestone=m, filepath=str(pending_dest), version="1", date_uploaded=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_date=parsed[3] if parsed and len(parsed) > 3 else "", status="uploaded")
                except Exception:
                    pass
            return {
                "file": filename, "doc_type": doc_type, "site_code": site_code,
                "milestones": milestones, "status": "pending_visual", "dests": [str(pending_dest)],
                "issues": issues,
            }

        # Ensure site folders exist
        mgr = SharePointManager()
        mgr.ensure_site_folders(site_code)

        # Copy to Review/[SITE]/[MS]/
        dests = []
        for ms in milestones:
            review_dir = self._get_review_milestone_dir(site_code, ms)
            review_dir.mkdir(parents=True, exist_ok=True)
            dest = review_dir / filename
            shutil.copy2(str(pdf_path), str(dest))
            dests.append(str(dest))
            try:
                self.db.upsert_document(site_code, doc_type, filename, milestone=ms, filepath=str(dest), version="1", date_uploaded=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_date=parsed[3] if parsed and len(parsed) > 3 else "", status="uploaded")
            except Exception:
                pass

        # Cross-check: if all CC docs exist, validate content
        cc_required = {"PO", "DN", "BL", "PL", "SATP"}
        for ms in milestones:
            if ms != "CC":
                continue
            ms_dir = self._get_review_milestone_dir(site_code, ms)
            existing = set()
            for f in ms_dir.glob("*.pdf"):
                dt = self._identify_doc_type(f.name)
                if dt in cc_required:
                    existing.add(dt)
            if existing == cc_required:
                cc_result = self.cross_check_cc_docs(site_code)
                if cc_result["status"] == "undetermined":
                    for d in dests:
                        Path(d).unlink(missing_ok=True)
                    pending_dir = self.pending_visual_root / site_code / ms
                    pending_dir.mkdir(parents=True, exist_ok=True)
                    pending_dest = pending_dir / filename
                    issues_cc = ["Cross-check undetermined: " + "; ".join(cc_result.get("issues", []))]
                    with open(str(pending_dest) + ".issues", "w") as f:
                        json.dump({"issues": issues_cc, "source": "cross_check", "details": cc_result}, f)
                    shutil.move(str(pdf_path), str(pending_dest))
                    try:
                        self.db.upsert_document(site_code, doc_type, filename, milestone=ms, filepath=str(pending_dest), version="1", date_uploaded=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_date=parsed[3] if parsed and len(parsed) > 3 else "", status="uploaded")
                    except Exception:
                        pass
                    return {
                        "file": filename, "doc_type": doc_type, "site_code": site_code,
                        "milestones": milestones, "status": "pending_visual",
                        "dests": [str(pending_dest)],
                        "issues": issues_cc, "cross_check": cc_result,
                    }
                elif not cc_result["passed"]:
                    issues_cc = ["Cross-check needs PMC visual validation: " + "; ".join(cc_result["issues"])]
                    for d in dests:
                        Path(d).unlink(missing_ok=True)
                    pending_dir = self.pending_visual_root / site_code / ms
                    pending_dir.mkdir(parents=True, exist_ok=True)
                    pending_dest = pending_dir / filename
                    with open(str(pending_dest) + ".issues", "w") as f:
                        json.dump({"issues": issues_cc, "source": "cross_check", "details": cc_result}, f)
                    shutil.move(str(pdf_path), str(pending_dest))
                    try:
                        self.db.upsert_document(site_code, doc_type, filename, milestone=ms, filepath=str(pending_dest), version="1", date_uploaded=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_date=parsed[3] if parsed and len(parsed) > 3 else "", status="uploaded")
                    except Exception:
                        pass
                    return {
                        "file": filename, "doc_type": doc_type, "site_code": site_code,
                        "milestones": milestones, "status": "pending_visual",
                        "dests": [str(pending_dest)],
                        "issues": issues_cc, "cross_check": cc_result,
                    }

        # Remove original from hot folder
        for retry in range(3):
            try:
                if pdf_path.exists():
                    pdf_path.unlink()
                break
            except PermissionError:
                import time
                time.sleep(0.5)

        # Auto-notify if ready
        if doc_type == "TSSR":
            _notify_if_ready(site_code, [ms for ms in milestones if ms == "CC"])

        return {
            "file": filename, "doc_type": doc_type, "site_code": site_code,
            "milestones": milestones, "status": "processed", "dests": dests,
            "issues": [],
        }

    def process_hot_folder(self, auto_rename=True):
        results = []
        for f in sorted(self.hot_folder.glob("*.pdf")):
            result = self.process_file(f, auto_rename=auto_rename)
            results.append(result)
        return results

    def watch_hot_folder(self, interval=10, once=False):
        import time
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class HotFolderHandler(FileSystemEventHandler):
            def __init__(self, agent):
                self.agent = agent

            def on_created(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.suffix.lower() == ".pdf":
                    time.sleep(1)
                    result = self.agent.process_file(event.src_path)
                    status = result["status"]
                    print(f"  [PDF {status}] {path.name}")
                elif path.suffix.lower() in (".xlsx", ".xls"):
                    time.sleep(1)
                    from agents.tracker_sync import sync_tracker_file
                    try:
                        result = sync_tracker_file(str(path))
                        status = result.get("status", "error")
                        print(f"  [TRACKER {status}] {path.name}")
                    except Exception as e:
                        print(f"  [TRACKER ERROR] {path.name}: {e}")

        handler = HotFolderHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self.hot_folder), recursive=False)
        observer.start()
        print(f"Watching hot_folder: {self.hot_folder}")
        if once:
            import time as t
            t.sleep(interval)
            observer.stop()
        else:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
        observer.join()


# ── CLI Functions ──

def cmd_setup_folders():
    mgr = SharePointManager()
    result = mgr.ensure_folder_structure()
    print(json.dumps(result, indent=2))


def cmd_validate_folders():
    mgr = SharePointManager()
    result = mgr.validate_structure()
    print(json.dumps(result, indent=2))


def cmd_archive_run():
    mgr = SharePointManager()
    result = mgr.run_archive_cycle()
    print(json.dumps(result, indent=2))


def cmd_archive_watch():
    mgr = SharePointManager()
    mgr.watch_archive()


def cmd_delta():
    mgr = SharePointManager()
    result = mgr.delta_query()
    print(json.dumps(result, indent=2))


def cmd_dc_log(args=None):
    mgr = SharePointManager()
    limit = int(args[0]) if args and args[0].isdigit() else 50
    rows = mgr.db.get_archive_log(limit=limit)
    print(json.dumps(rows, indent=2))


def cmd_dc_summary():
    mgr = SharePointManager()
    print(json.dumps(mgr.db.get_archive_log(limit=1000), indent=2))


def cmd_submit_process():
    agent = SubmitAgent()
    result = agent.process_hot_folder()
    print(json.dumps(result, indent=2))


def cmd_submit_verify(doc_type=None):
    agent = SubmitAgent()
    review_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Review"
    if not review_root.exists():
        print("No review folder")
        return
    for site_dir in sorted(review_root.iterdir()):
        if not site_dir.is_dir():
            continue
        for ms_dir in sorted(site_dir.iterdir()):
            if not ms_dir.is_dir() or ms_dir.name not in MILESTONES:
                continue
            for f in sorted(ms_dir.glob("*.pdf")):
                dt = SubmitAgent._identify_doc_type(f.name)
                if doc_type and dt != doc_type:
                    continue
                result = agent.verify_document(f)
                status = "PASS" if result.get("passed") else "FAIL"
                print(f"  [{status}] {site_dir.name}/{ms_dir.name}/{f.name}")
                if not result.get("passed"):
                    for issue in result.get("issues", []):
                        print(f"         {issue}")


def cmd_submit_watch():
    agent = SubmitAgent()
    agent.watch_hot_folder(interval=WATCH_INTERVAL_SECONDS)


def cmd_auto_rename():
    agent = SubmitAgent()
    hot = agent.hot_folder
    files = list(hot.glob("*.pdf"))
    if not files:
        print("No PDFs in hot_folder.")
        return
    renamed = 0
    for f in files:
        new_path = agent._auto_rename(f)
        if new_path != f:
            print(f"  Renamed: {f.name} -> {new_path.name}")
            renamed += 1
        else:
            print(f"  Skipped: {f.name}")
    print(f"Renamed {renamed}/{len(files)} files")


def cmd_submit_status():
    agent = SubmitAgent()
    review_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Review"
    hot_count = len(list(agent.hot_folder.glob("*.pdf")))
    failed_count = len(list(agent.failed_folder.glob("*")))
    review_total = 0
    site_ms_count = 0
    if review_root.exists():
        for site_dir in review_root.iterdir():
            if not site_dir.is_dir():
                continue
            for ms_dir in site_dir.iterdir():
                if not ms_dir.is_dir() or ms_dir.name not in MILESTONES:
                    continue
                files = list(ms_dir.glob("*.pdf"))
                if files:
                    review_total += len(files)
                    site_ms_count += 1

    print(f"Pipeline Status:")
    print(f"  Hot folder pending: {hot_count}")
    print(f"  Failed:             {failed_count}")
    print(f"  Review folders:     {site_ms_count}")
    print(f"  Review total files: {review_total}")


def cmd_review_status():
    mgr = SharePointManager()
    reviews = mgr.scan_review_folders()
    if not reviews:
        print("No review folders found.")
        return
    header = f"{'Site':12s} {'Milestone':10s} {'Files':6s} {'Ready?':6s} {'Missing Docs'}"
    print(header)
    print("-" * len(header))
    ready_count = 0
    for r in reviews:
        ready = "YES" if r["all_docs_present"] else "NO"
        missing = ", ".join(r["missing_docs"]) if r["missing_docs"] else "-"
        print(f"{r['site_code']:12s} {r['milestone']:10s} {r['file_count']:4d}   {ready:6s} {missing}")
        if r["all_docs_present"] and r["file_count"] > 0:
            ready_count += 1
    print(f"\n{ready_count} milestone(s) ready for approval.")


def cmd_approve_ready():
    agent = SubmitAgent()
    mgr = SharePointManager()
    ready = mgr.get_approval_ready_list()
    if not ready:
        print("No milestones ready for approval.")
        return
    print(f"{'Site':12s} {'Milestone':10s} {'Files':6s} {'CrossChk':8s}")
    print("-" * 40)
    total = 0
    for r in ready:
        cc_status = "N/A"
        if r["milestone"] == "CC":
            xc = agent.cross_check_cc_docs(r["site_code"])
            if xc["status"] == "undetermined":
                cc_status = "UND"
            else:
                cc_status = "PASS" if xc["passed"] else "FAIL"
        print(f"{r['site_code']:12s} {r['milestone']:10s} {r['file_count']:4d}   {cc_status:8s}")
        if cc_status in ("PASS", "N/A"):
            total += 1
    print(f"\nTotal: {total} milestone(s) ready for approval.")


def _notify_if_ready(site_code, milestones=None):
    from agents.database import DatabaseAgent
    from agents.notification_service import generate_readiness_pdf, send_notification_email
    db = DatabaseAgent()
    agent = SubmitAgent()
    mgr = SharePointManager()
    if milestones is None:
        milestones = MILESTONES
    for ms in milestones:
        r = mgr.scan_review_folders(site_code=site_code)
        r = [x for x in r if x["milestone"] == ms]
        if not r:
            continue
        r = r[0]
        if not r["all_docs_present"] or r["file_count"] == 0:
            continue
        cc_status = "N/A"
        if ms == "CC":
            xc = agent.cross_check_cc_docs(site_code)
            if xc["status"] == "undetermined":
                cc_status = "UND"
            else:
                cc_status = "PASS" if xc["passed"] else "FAIL"
            if xc["status"] in ("fail", "undetermined"):
                continue
        existing = db.connect().execute(
            "SELECT id FROM notifications WHERE site_code=? AND milestone=? AND notification_type='ready_for_review'",
            (site_code, ms)
        ).fetchone()
        if existing:
            continue
        review_dir = mgr._get_sites_doc_working_root() / "Review" / site_code / ms
        doc_list = []
        if review_dir.exists():
            for f in sorted(review_dir.glob("*.pdf")):
                dt = SubmitAgent._identify_doc_type(f.name) or "Unknown"
                try:
                    import fitz
                    doc = fitz.open(str(f))
                    pages = doc.page_count
                    doc.close()
                except Exception:
                    pages = "?"
                doc_list.append({
                    "filename": f.name, "doc_type": dt, "pages": str(pages),
                    "status": "pass", "size_kb": f.stat().st_size / 1024,
                })
        cross_check_label = cc_status if ms == "CC" else "N/A"
        pdf_path = generate_readiness_pdf(site_code, ms, doc_list, cross_check_label, None)
        result = send_notification_email(site_code, ms, pdf_path)
        if result["status"] == "sent":
            print(f"  Auto-notification sent: {site_code}/{ms}")
        elif result["status"] == "skipped":
            print(f"  Auto-notification skipped (SMTP not configured): {site_code}/{ms}")
        details = (
            f"Site {site_code} milestone {ms} is ready for review. "
            f"All {r['file_count']} required document(s) present and validated. "
            f"Cross-check: {cross_check_label}. PDF: {pdf_path}"
        )
        db.upsert_notification(site_code, ms, details=details)
        conn = db.connect()
        row = conn.execute(
            "SELECT id FROM notifications WHERE site_code=? AND milestone=? AND notification_type='ready_for_review'",
            (site_code, ms)
        ).fetchone()
        conn.close()
        if row:
            db.mark_notification_sent(row["id"])


def cmd_notify_ready():
    from agents.database import DatabaseAgent
    db = DatabaseAgent()
    agent = SubmitAgent()
    mgr = SharePointManager()
    reviews = mgr.scan_review_folders()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = 0
    emails_sent = 0
    for r in reviews:
        if not r["all_docs_present"] or r["file_count"] == 0:
            continue
        _notify_if_ready(r["site_code"], [r["milestone"]])
    all_notes = db.get_notifications()
    print(f"{'='*60}")
    print(f"Notification Report: {now}")
    print(f"  New notifications: {count}")
    print(f"  Emails sent: {emails_sent}")
    if all_notes:
        print(f"\n  {'Site':12s} {'Milestone':10s} {'Status':10s} {'Created'}")
        print(f"  {'-'*44}")
        for n in all_notes:
            print(f"  {n['site_code']:12s} {n['milestone']:10s} {n['status']:10s} {n['created_at']}")
    print(f"{'='*60}")
    log_dir = Path("notifications")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "ready_for_review.log"
    with open(log_path, "a") as f:
        f.write(f"\n--- {now} ---\n")
        for n in all_notes:
            f.write(f"[{n['status']}] {n['site_code']}/{n['milestone']}: {n['details']}\n")
    print(f"  Log written to: {log_path}")
    print(f"{'='*60}")


def cmd_pending_visual_status():
    mgr = SharePointManager()
    items = mgr.scan_pending_visual_folders()
    if not items:
        print("No documents pending visual check.")
        return
    header = f"{'Site':12s} {'Milestone':10s} {'Files':6s} {'Doc Types'}"
    print(header)
    print("-" * 60)
    for r in items:
        types = ", ".join(r["doc_types"])
        print(f"{r['site_code']:12s} {r['milestone']:10s} {r['file_count']:4d}   {types}")
    total = sum(r["file_count"] for r in items)
    print(f"\nTotal: {len(items)} site/milestone(s), {total} file(s) pending visual check.")
    print("Run 'sp-visual-approve <SITE> <MS>' after PMC confirms cross-check passes.")


def cmd_visual_approve():
    """Move files from Pending_Visual_Check to Review after PMC confirmation."""
    if len(sys.argv) < 4:
        print("Usage: python run.py sp-visual-approve <SITENAME> <MILESTONE>")
        return
    site_code = sys.argv[2].upper()
    milestone = sys.argv[3].upper()
    mgr = SharePointManager()
    pv_dir = mgr._get_sites_doc_working_root() / "Pending_Visual_Check" / site_code / milestone
    if not pv_dir.exists():
        print(f"No pending visual folder: {pv_dir}")
        return
    files = list(pv_dir.glob("*.pdf"))
    if not files:
        print("No files to move.")
        return
    review_dir = mgr._get_sites_doc_working_root() / "Review" / site_code / milestone
    review_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    for f in files:
        dest = review_dir / f.name
        shutil.move(str(f), str(dest))
        moved.append(f.name)
    remaining = list(pv_dir.glob("*"))
    if not remaining:
        pv_dir.rmdir()
        parent = pv_dir.parent
        if parent.exists() and not list(parent.iterdir()):
            parent.rmdir()
    print(f"Moved {len(moved)} file(s) to Review/{site_code}/{milestone}/")
    for m in moved:
        print(f"  {m}")
    _notify_if_ready(site_code, [milestone])


def cmd_approve_milestone():
    """Approve a milestone: python run.py sp-approve <SITENAME> <MILESTONE>"""
    if len(sys.argv) < 4:
        print("Usage: python run.py sp-approve <SITENAME> <MILESTONE>")
        print("  MILESTONE: CC, PAC, FAC")
        return
    site_code = sys.argv[2]
    milestone = sys.argv[3].upper()
    if milestone == "CC":
        agent = SubmitAgent()
        xc = agent.cross_check_cc_docs(site_code)
        if xc["status"] == "undetermined":
            print(f"Cross-check UNDETERMINED — OCR gibberish, needs PMC visual confirmation.")
            print(f"Docs requiring OCR: {', '.join(xc['details'].get('ocr_docs', []))}")
            return
        if not xc["passed"]:
            print(f"Cross-check FAILED: {'; '.join(xc['issues'])}")
            print("Fix content issues or run sp-cross-check for details.")
            return
    mgr = SharePointManager()
    result = mgr.approve_milestone(site_code, milestone)
    print(json.dumps(result, indent=2))
