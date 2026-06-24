"""Dashboard server — Python http.server + ThreadingTCPServer on localhost:8080."""
import json
import io
import re
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
from email.parser import BytesParser
from email.policy import HTTP

from agents.database import DatabaseAgent
from agents.config import BASE_DIR


class DashboardHandler(BaseHTTPRequestHandler):
    db = DatabaseAgent()

    def do_GET(self):
        path = self.path.split("?")[0]
        routes = {
            "/": self._serve_dashboard,
            "/dashboard.html": self._serve_dashboard,
            "/data_viewer.html": self._serve_data_viewer,
            "/checklist.html": self._serve_checklist,
            "/dc.html": self._serve_dc,
            "/api/summary": self._api_summary,
            "/api/stats": self._api_stats,
            "/api/sites": self._api_sites,
            "/api/site": self._api_site_detail,
            "/api/milestones": self._api_milestones,
            "/api/documents": self._api_documents,
            "/api/verification": self._api_verification,
            "/api/verification_summary": self._api_verification_summary,
            "/api/verification_checklist": self._api_verification_checklist,
            "/api/date_changes": self._api_date_changes,
            "/api/date_changes_summary": self._api_date_changes_summary,
            "/api/unauthorized_date_changes": self._api_date_changes,
            "/api/tracker_audit": self._api_tracker_audit,
            "/api/audit": self._api_audit_log,
            "/api/pipeline_status": self._api_pipeline_status,
            "/api/process_pipeline": self._api_process_pipeline,
            "/api/review_status": self._api_review_status,
            "/api/approval_ready": self._api_approval_ready,
            "/api/alerts": self._api_alerts,
            "/api/progress_summary": self._api_progress_summary,
            "/api/regions": self._api_regions,
            "/api/overall_statuses": self._api_overall_statuses,
            "/api/refresh": self._api_refresh,
            "/api/pending_validate": self._api_pending_validate,
            "/api/view_file": self._api_view_file,
        }
        handler = routes.get(path)
        if handler:
            handler()
        elif self.path.startswith("/api/"):
            self._json_response({"error": "Not found"}, 404)
        else:
            self._serve_static(self.path.lstrip("/"))

    def do_POST(self):
        if self.path == "/api/upload":
            self._api_upload()
        elif self.path == "/api/validate":
            self._api_validate()
        else:
            self._json_response({"error": "Not found"}, 404)

    def _serve_dashboard(self):
        self._serve_static("dashboard.html")

    def _serve_data_viewer(self):
        self._serve_static("data_viewer.html")

    def _serve_checklist(self):
        self._serve_static("checklist.html")

    def _serve_dc(self):
        self._serve_static("dc.html")

    def _serve_static(self, filename):
        filepath = BASE_DIR / filename
        if not filepath.exists():
            self.send_error(404, "File not found")
            return
        ext = filepath.suffix.lower()
        types = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
                 ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml",
                 ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        self.send_response(200)
        self.send_header("Content-Type", types.get(ext, "application/octet-stream"))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(filepath, "rb") as f:
            self.wfile.write(f.read())

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    # ── API Handlers ──

    def _api_summary(self):
        stats = self.db.get_summary_stats()
        sites = self.db.get_all_sites()
        node_counts = {"ACC": 0, "IPCORE": 0, "TRUNK": 0, "RNC": 0}
        for s in sites:
            nt = (s.get("node_type") or "").upper()
            for t in ["ACC", "IPCORE", "TRUNK", "RNC"]:
                if t in nt:
                    node_counts[t] += 1
        stats["by_tracker"] = node_counts
        self._json_response(stats)

    def _api_stats(self):
        stats = self.db.get_summary_stats()
        sites = self.db.get_all_sites()
        node_counts = {"ACC": 0, "IPCORE": 0, "TRUNK": 0, "RNC": 0}
        for s in sites:
            nt = (s.get("node_type") or "").upper()
            for t in ["ACC", "IPCORE", "TRUNK", "RNC"]:
                if t in nt:
                    node_counts[t] += 1
        ms_rows = self.db.get_milestone_status()
        site_ms = {}
        for m in ms_rows:
            site_ms.setdefault(m["site_code"], {})[m["milestone"]] = m["status"]
        fully = any_ongoing = not_started = 0
        milestones = ["CC", "PAC", "FAC"]
        for sc, st in site_ms.items():
            all_not = all(st.get(ms, "Not started") == "Not started" for ms in milestones)
            all_done = all(st.get(ms) == "Completed" for ms in milestones)
            if all_done:
                fully += 1
            elif all_not:
                not_started += 1
            else:
                any_ongoing += 1
        stats["fully_completed"] = fully
        stats["any_ongoing"] = any_ongoing
        stats["not_started"] = not_started
        stats["by_tracker"] = node_counts
        self._json_response(stats)

    def _api_sites(self):
        sites = self.db.get_all_sites()
        self._json_response(sites)

    def _api_site_detail(self):
        code = self._get_param("code")
        if not code:
            self._json_response({"error": "site code required"}, 400)
            return
        site = self.db.get_site(code)
        docs = self.db.get_documents(site_code=code)
        ms = self.db.get_milestone_status(site_code=code)
        ms_required = {
            "CC": ["PO", "DN", "BL", "PL", "TSSR", "SATP"],
            "PAC": ["PO", "MOP", "SMR", "CC", "PAF"],
            "FAC": ["PO", "PAF", "FAF"],
        }
        detail = []
        for m in ms:
            uploaded = {d["doc_type"] for d in docs if d.get("milestone") == m["milestone"]}
            required = ms_required.get(m["milestone"], [])
            missing = [r for r in required if r not in uploaded]
            detail.append({
                "milestone": m["milestone"],
                "status": m["status"],
                "actual_date": m.get("actual_date", ""),
                "all_docs_uploaded": len(missing) == 0,
                "missing_docs": missing,
            })
        os_val = self.db.get_activity_value(code, "IP Bearer Network", "Overall Status")
        self._json_response({
            "site": dict(site) if site else {},
            "documents": docs,
            "milestones": ms,
            "milestone_detail": detail,
            "overall_status": os_val or "",
            "overall_remark": "",
        })

    def _api_milestones(self):
        site = self._get_param("site")
        ms_rows = self.db.get_milestone_status(site_code=site)
        self._json_response(ms_rows)

    def _api_progress_summary(self):
        ms = self.db.get_milestone_status()
        result = {}
        for m in ms:
            ml = m["milestone"]
            if ml not in result:
                result[ml] = {"completed": 0, "ongoing": 0, "not_started": 0, "completion_pct": 0, "completed_by_node": {}}
            st = m["status"].lower().replace(" ", "_")
            if st == "completed":
                result[ml]["completed"] += 1
            elif "ongoing" in st or "in_progress" in st:
                result[ml]["ongoing"] += 1
            else:
                result[ml]["not_started"] += 1
        # Add node_type breakdown for completed milestones
        # Split compound node_types into 4 core categories: ACC, IPCORE, TRUNK, RNC
        conn = self.db.connect()
        rows = conn.execute("""
            SELECT ms.milestone, s.node_type, COUNT(*) as cnt
            FROM milestone_status ms
            JOIN sites s ON s.site_code = ms.site_code
            WHERE ms.status = 'Completed'
            GROUP BY ms.milestone, s.node_type
        """).fetchall()
        conn.close()
        core_types = {"ACC", "IPCORE", "TRUNK", "RNC"}
        for r in rows:
            ml = r["milestone"]
            if ml not in result:
                continue
            nt_raw = (r["node_type"] or "").upper()
            parts = [x.strip() for x in nt_raw.replace(",", " ").replace(";", " ").split() if x.strip() in core_types]
            cnt = r["cnt"]
            for pt in parts:
                result[ml]["completed_by_node"][pt] = result[ml]["completed_by_node"].get(pt, 0) + cnt
        for ml, d in result.items():
            total = d["completed"] + d["ongoing"] + d["not_started"]
            d["completion_pct"] = round(d["completed"] / total * 100, 1) if total else 0
        # Enforce order: CC, PAC, FAC
        ordered = {}
        for ml in ["CC", "PAC", "FAC"]:
            if ml in result:
                ordered[ml] = result[ml]
        self._json_response(ordered)

    def _api_regions(self):
        sites = self.db.get_all_sites()
        regions = {}
        for s in sites:
            r = s.get("region") or "Unknown"
            if r not in regions:
                regions[r] = {"total": 0, "fac_completed": 0}
            regions[r]["total"] += 1
        ms = self.db.get_milestone_status()
        fac_sites = set()
        for m in ms:
            if m["milestone"] == "FAC" and m["status"] == "Completed":
                fac_sites.add(m["site_code"])
        for s in sites:
            if s["site_code"] in fac_sites:
                r = s.get("region") or "Unknown"
                if r in regions:
                    regions[r]["fac_completed"] += 1
        self._json_response(regions)

    def _api_alerts(self):
        from agents.config import SHAREPOINT_SIM_DIR, SITES_DOC_AREA
        ms = self.db.get_milestone_status()
        alerts = []
        # High: milestones "Completed" but missing required docs (via Review folder scan)
        from agents.sharepoint_manager import SharePointManager
        mgr = SharePointManager()
        reviews = mgr.scan_review_folders()
        for r in reviews:
            if r.get("all_docs_present") == False:
                alerts.append({
                    "severity": "high", "message": f"Completed milestone missing docs",
                    "site_code": r["site_code"], "milestone": r["milestone"]
                })
        # Medium: sites stuck in Pending_Visual_Check
        pv_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Pending_Visual_Check"
        if pv_root.exists():
            for site_dir in sorted(pv_root.iterdir()):
                if not site_dir.is_dir(): continue
                pdfs = list(site_dir.rglob("*.pdf"))
                if pdfs:
                    alerts.append({
                        "severity": "medium", "message": f"{len(pdfs)} doc(s) pending visual check",
                        "site_code": site_dir.name, "milestone": ""
                    })
        # Info: tracker audit summary
        audits = self.db.get_tracker_audit(limit=50)
        if audits:
            alerts.append({
                "severity": "info", "message": f"{len(audits)} recent tracker changes",
                "site_code": "", "milestone": ""
            })
        self._json_response(alerts)

    def _api_overall_statuses(self):
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT site_code, value FROM site_activities WHERE activity_name='IP Bearer Network' AND field_name='Overall Status'"
        ).fetchall()
        conn.close()
        result = {r["site_code"]: r["value"] for r in rows if r["value"]}
        self._json_response(result)

    def _api_refresh(self):
        """Refresh: run any pending hot folder processing, then return status."""
        import threading, os, sys
        from pathlib import Path
        from agents.config import SHAREPOINT_SIM_DIR, SITES_DOC_AREA, SITES_DOC_SUBMIT

        hot = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / SITES_DOC_SUBMIT
        pending = list(hot.glob("*.pdf"))
        if pending:
            def _process():
                from agents.sharepoint_manager import SubmitAgent
                sa = SubmitAgent()
                sa.process_hot_folder(auto_rename=True)
            t = threading.Thread(target=_process, daemon=True)
            t.start()
            self._json_response({"status": "processing", "pending": len(pending), "started": True})
        else:
            self._json_response({"status": "ok", "pending": 0})

    def _api_tracker_audit(self):
        rows = self.db.get_tracker_audit(limit=200)
        self._json_response(rows)

    def _api_audit_log(self):
        rows = self.db.get_audit_log(limit=200)
        self._json_response(rows)

    def _api_process_pipeline(self):
        from agents.config import SHAREPOINT_SIM_DIR, SITES_DOC_AREA, SITES_DOC_SUBMIT
        sites = self.db.get_all_sites()
        hot_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / SITES_DOC_SUBMIT
        pv_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Pending_Visual_Check"
        review_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Review"
        approve_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Approve"
        failed_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / SITES_DOC_SUBMIT / "_failed"
        hot_count = len(list(hot_root.glob("*.pdf"))) if hot_root.exists() else 0
        pv_count = sum(1 for _ in pv_root.rglob("*.pdf")) if pv_root.exists() else 0
        review_count = sum(1 for _ in review_root.rglob("*.pdf")) if review_root.exists() else 0
        approve_count = sum(1 for _ in approve_root.rglob("*.pdf")) if approve_root.exists() else 0
        failed_count = len(list(failed_root.glob("*.pdf"))) if failed_root.exists() else 0
        pipeline = [
            {"stage": "Hot Folder", "count": hot_count},
            {"stage": "Pending Visual Check", "count": pv_count},
            {"stage": "Review", "count": review_count},
            {"stage": "Approve", "count": approve_count},
            {"stage": "Failed", "count": failed_count},
        ]
        self._json_response(pipeline)

    def _api_documents(self):
        site = self._get_param("site")
        doc_type = self._get_param("doc_type")
        docs = self.db.get_documents(site_code=site, doc_type=doc_type)
        self._json_response(docs)

    def _api_verification(self):
        doc_type = self._get_param("doc_type")
        status = self._get_param("status")
        rows = self.db.get_all_verifications(doc_type=doc_type, status=status)
        self._json_response(rows)

    def _api_verification_summary(self):
        summary = self.db.get_verification_summary()
        self._json_response(summary)

    def _api_verification_checklist(self):
        milestone = self._get_param("milestone")
        search = (self._get_param("search") or "").upper().strip()
        limit = int(self._get_param("limit") or 200)
        checklist = self.db.get_verification_checklist(milestone_filter=milestone, search=search, limit=limit)
        self._json_response(checklist)

    def _api_date_changes(self):
        limit = int(self._get_param("limit") or 100)
        rows = self.db.get_unauthorized_date_changes(limit=limit)
        self._json_response(rows)

    def _api_date_changes_summary(self):
        rows = self.db.get_date_changes_summary()
        total = sum(r["cnt"] for r in rows)
        overwrites = sum(r["overwrites"] for r in rows)
        additions = sum(r["new_entries"] for r in rows)
        self._json_response({"total": total, "overwrites": overwrites, "additions": additions})

    def _api_pipeline_status(self):
        from agents.sharepoint_manager import cmd_submit_status
        import io, sys
        captured = io.StringIO()
        sys.stdout = captured
        try:
            cmd_submit_status()
        finally:
            sys.stdout = sys.__stdout__
        self._json_response({"output": captured.getvalue()})

    def _api_review_status(self):
        from agents.sharepoint_manager import SharePointManager
        mgr = SharePointManager()
        reviews = mgr.scan_review_folders()
        self._json_response(reviews)

    def _api_approval_ready(self):
        from agents.sharepoint_manager import SharePointManager
        mgr = SharePointManager()
        ready = mgr.get_approval_ready_list()
        self._json_response(ready)

    def _api_upload(self):
        """Handle file upload to hot folder."""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._json_response({"error": "Expected multipart/form-data"}, 400)
            return

        from agents.config import SITES_DOC_AREA, SITES_DOC_SUBMIT
        from agents.sharepoint_manager import SHAREPOINT_SIM_DIR
        hot_dir = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / SITES_DOC_SUBMIT
        hot_dir.mkdir(parents=True, exist_ok=True)

        raw = self.rfile.read(int(self.headers.get("content-length", 0)))
        boundary = content_type.split("boundary=", 1)[1].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]
        msg = BytesParser(policy=HTTP).parsebytes(
            b"Content-Type: multipart/mixed; boundary=" + boundary.encode() + b"\r\n\r\n" + raw
        )
        uploaded = []
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            filename = part.get_filename()
            if filename:
                filename_clean = Path(filename).name
                dest = hot_dir / filename_clean
                with open(str(dest), "wb") as f:
                    f.write(part.get_payload(decode=True))
                uploaded.append(filename_clean)
        self._json_response({"uploaded": uploaded, "count": len(uploaded)})

    def _api_pending_validate(self):
        """List files in Pending_Visual_Check needing PMC validation."""
        import json as json_mod
        from agents.config import SHAREPOINT_SIM_DIR, SITES_DOC_AREA
        from agents.sharepoint_manager import SubmitAgent
        pv_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Pending_Visual_Check"
        review_root = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Review"
        entries = []
        if pv_root.exists():
            for site_dir in sorted(pv_root.iterdir()):
                if not site_dir.is_dir():
                    continue
                site_code = site_dir.name
                # Collect PDFs from root dir and subdirs
                subdirs = [d for d in sorted(site_dir.iterdir()) if d.is_dir()]
                pdf_files = list(site_dir.glob("*.pdf"))
                # Also collect .issues-only entries (PDF missing)
                for sd in subdirs:
                    pdf_files += list(sd.glob("*.pdf"))
                # Sites with only .issues files (no PDF) — add placeholder entries
                has_issues_no_pdf = []
                if not pdf_files:
                    for sf in sorted(site_dir.iterdir()):
                        if sf.suffix == ".issues":
                            has_issues_no_pdf.append(("", sf))
                    for sd in subdirs:
                        for sf in sorted(sd.iterdir()):
                            if sf.suffix == ".issues":
                                expected_pdf = sf.parent / sf.name.replace(".issues", "")
                                if not expected_pdf.exists():
                                    has_issues_no_pdf.append((sd, sf))
                pdf_dirs = [site_dir] if pdf_files else []
                pdf_dirs += subdirs
                for ms_dir in pdf_dirs:
                    ms_name = ms_dir.name if ms_dir.parent == site_dir else site_dir.name
                    for f in sorted(ms_dir.glob("*.pdf")):
                        doc_type = SubmitAgent._identify_doc_type(f.name)
                        rel = f.relative_to(pv_root)
                        issues_file = f.parent / (f.name + ".issues")
                        issues = []
                        cc_details = {}
                        if issues_file.exists():
                            try:
                                data = json_mod.loads(issues_file.read_text())
                                issues = data.get("issues", [])
                                cc_details = data.get("details", {})
                            except Exception:
                                pass
                        # Find related docs in Review folder
                        related = []
                        if ms_dir.parent == site_dir:
                            rel_review = review_root / site_code / ms_name
                            if rel_review.exists():
                                for rpdf in sorted(rel_review.glob("*.pdf")):
                                    rdt = SubmitAgent._identify_doc_type(rpdf.name)
                                    if rdt and rdt != doc_type:
                                        related.append({
                                            "doc_type": rdt,
                                            "filename": rpdf.name,
                                            "path": str(rpdf),
                                            "size_kb": round(rpdf.stat().st_size / 1024, 1),
                                        })
                        entries.append({
                            "site": site_code,
                            "milestone": ms_name,
                            "doc_type": doc_type or "Unknown",
                            "filename": f.name,
                            "path": str(f),
                            "rel_path": str(rel),
                            "size_kb": round(f.stat().st_size / 1024, 1),
                            "issues": issues,
                            "cc_details": cc_details,
                            "file_missing": False,
                            "related_docs": related,
                        })
                # Add .issues-only placeholder entries (PDF missing)
                for sd, sf in has_issues_no_pdf:
                    ms_name = sd.name if sd else site_dir.name
                    try:
                        data = json_mod.loads(sf.read_text())
                        issues = data.get("issues", ["PDF not found — only .issues sidecar remains"])
                        cc_details = data.get("details", {})
                    except Exception:
                        issues = ["PDF not found — only .issues sidecar remains"]
                        cc_details = {}
                    entries.append({
                        "site": site_code,
                        "milestone": ms_name,
                        "doc_type": "Unknown",
                        "filename": sf.name.replace(".issues", ""),
                        "path": "",
                        "rel_path": str(sf.relative_to(pv_root)),
                        "size_kb": 0,
                        "issues": issues,
                        "cc_details": cc_details,
                        "file_missing": True,
                        "related_docs": [],
                    })
        self._json_response(entries)

    def _api_validate(self):
        """Move file from Pending_Visual_Check to Review/[site]/[ms]/, cleanup .issues sidecar."""
        import json, shutil
        from agents.config import SHAREPOINT_SIM_DIR, SITES_DOC_AREA
        raw = self.rfile.read(int(self.headers.get("content-length", 0)))
        data = json.loads(raw)
        path = data.get("path", "")
        fp = Path(path)
        if not fp.exists():
            self._json_response({"success": False, "error": "File not found"}, 404)
            return
        site = data.get("site") or fp.parent.parent.name
        ms = data.get("milestone") or fp.parent.name
        review_dir = SHAREPOINT_SIM_DIR / "Working" / SITES_DOC_AREA / "Review" / site.upper() / ms
        review_dir.mkdir(parents=True, exist_ok=True)
        dest = review_dir / fp.name
        shutil.move(str(fp), str(dest))
        # Update document DB record
        try:
            from agents.extract_base import _parse_filename
            parsed = _parse_filename(fp.name)
            doc_type = parsed[0] if parsed else ""
            self.db.upsert_document(site.upper(), doc_type, fp.name, milestone=ms.upper(), filepath=str(dest), version="1", date_uploaded=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_date=parsed[3] if parsed and len(parsed) > 3 else "", status="uploaded")
        except Exception:
            pass
        # Cleanup .issues sidecar if exists
        issues_file = fp.parent / (fp.name + ".issues")
        if issues_file.exists():
            issues_file.unlink()
        self._json_response({"success": True, "dest": str(dest)})

    def _api_view_file(self):
        """Serve a file from Pending_Visual_Check for viewing."""
        path = self._get_param("path")
        if not path:
            self._json_response({"error": "path required"}, 400)
            return
        fp = Path(path)
        if not fp.exists():
            self._json_response({"error": "File not found"}, 404)
            return
        ext = fp.suffix.lower()
        types = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg"}
        self.send_response(200)
        self.send_header("Content-Type", types.get(ext, "application/octet-stream"))
        self.send_header("Content-Disposition", "inline")
        self.end_headers()
        with open(fp, "rb") as f:
            self.wfile.write(f.read())

    def _get_param(self, name):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        vals = params.get(name, [])
        return vals[0] if vals else None

    def log_message(self, format, *args):
        pass


def start_server(host="0.0.0.0", port=8080):
    server = ThreadingTCPServer((host, port), DashboardHandler)
    server.daemon_threads = True
    server.allow_reuse_address = True
    print(f"Dashboard running at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    start_server()
