#!/usr/bin/env python3
"""
SACOFA Reporting Automation Framework
Run: python run.py [command]

Commands:
  start       Start the dashboard server (default)
  extract     Batch extract PDFs from hot_folder
  sync        Run progress sync
  watch       Watch hot_folder for new files (ingestion agent)
  seed        Extract existing tracker PDFs into the DB
  export      Export full report to Excel
  status      Show database summary

SharePoint Folder Management:
  sp-setup    Create Working + Archive folder structure (local sim)
  sp-validate Check folder structure integrity
  sp-archive  Move all files from Working/Approve to Archive
  sp-watch    Continuously watch and archive approved files
  sp-delta    Run simulated delta query (show folder state changes)
  dc-log      Show Document Controller archive log
  dc-summary  Show DC archive summary stats

Submit Pipeline (Sites Document):
  sp-submit-status      Show document counts in pipeline
  sp-submit-process     Process files in hot_folder (batch)
  sp-submit-verify      Batch-verify quality of docs in Review folders
  sp-submit-watch       Watch hot_folder for new documents (continuous)
  sp-auto-rename   Batch auto-rename all files in hot_folder based on content
  sp-review-status Show Review folder readiness per site+milestone
  sp-approve-ready      List milestones ready for approval
  sp-approve <SITE> <M> Approve a milestone (Review → Approve)
  sp-cross-check <SITE> Cross-validate PO+DN+BL+PL for a site (site name, PO#)
  sp-notify-ready       Generate client notifications for milestones ready for review
  sp-pending-visual     Show docs needing PMC visual confirmation (OCR undetermined)
  sp-visual-approve <S> <M> Move from Pending_Visual_Check to Review after PMC OK
  sp-notify-pmc         Send email to PMC with list of items needing manual verification

File Renaming:
  rename      Preview rename: python run.py rename <folder>
              Apply rename:   python run.py rename <folder> --apply

Document Verification:
  verify        Run verification on all existing documents
  verify-status Show verification summary stats

Database:
  db-reset            Delete all data and recreate tables (fresh demo start)

Reports:
  rejected-docs-report  Generate rejected documents report (Excel + console)

GUI:
  watchdog-gui          Launch monitoring GUI with Go/Stop for watchdog
"""
import sys, os, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "agents"))
from config import HOT_FOLDER, BASE_DIR


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"

    if cmd == "start":
        from agents.dashboard_server import start_server
        port = int(os.environ.get("PORT", 8080))
        start_server(port=port)

    elif cmd == "extract":
        from agents.extraction_engine import batch_extract
        from agents.database import DatabaseAgent
        folder = sys.argv[2] if len(sys.argv) > 2 else str(HOT_FOLDER)
        db = DatabaseAgent()
        batch_extract(folder, db)

    elif cmd == "sync":
        from import_trackers import import_all_trackers
        from agents.tracker_sync import sync_tracker_file
        import_all_trackers()
        from import_trackers import TRACKER_FILES
        for nt, fp in TRACKER_FILES.items():
            print(f"\n--- Syncing activity data for {nt} ---")
            result = sync_tracker_file(fp)
            print(f"  Result: {result['status']}, sites={result.get('sites',0)}, milestones derived={result.get('milestones_derived',0)}")

    elif cmd == "watch":
        from agents.ingestion import IngestionAgent
        agent = IngestionAgent()
        try:
            agent.watch()
        except KeyboardInterrupt:
            agent.stop()
            print("\nStopped.")

    elif cmd == "export":
        from agents.database import DatabaseAgent
        from config import EXPORTS_DIR
        import openpyxl
        db = DatabaseAgent()
        data = db.export_full_report()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Full Report"
        if data:
            ws.append(list(data[0].keys()))
            for row in data:
                ws.append(list(row.values()))
        path = EXPORTS_DIR / "report.xlsx"
        wb.save(str(path))
        print(f"Exported {len(data)} rows to {path}")

    elif cmd == "status":
        from agents.database import DatabaseAgent
        db = DatabaseAgent()
        stats = db.get_summary_stats()
        print(f"Sites:     {stats['total_sites']}")
        print(f"Docs:      {stats['total_documents']}")
        for s in stats['milestone_status']:
            print(f"  {s['milestone']}: {s['status']} = {s['cnt']}")

    elif cmd == "sync-tracker":
        if len(sys.argv) > 2:
            from agents.tracker_sync import sync_tracker_file
            result = sync_tracker_file(sys.argv[2])
            print(f"Result: {result}")
        else:
            print("Usage: python run.py sync-tracker <path_to_tracker.xlsx>")

    elif cmd == "import":
        from import_trackers import import_all_trackers
        from agents.tracker_sync import sync_tracker_file
        import_all_trackers()
        from import_trackers import TRACKER_FILES
        for nt, fp in TRACKER_FILES.items():
            print(f"\n--- Syncing activity data for {nt} ---")
            sync_tracker_file(fp)

    elif cmd == "seed":
        print("To seed from tracker Excel files, run: python run.py import")
        print("To seed from TSSR data, run: python seed.py")

    # ── SharePoint Folder Management ──
    elif cmd == "sp-setup":
        from agents.sharepoint_manager import cmd_setup_folders
        cmd_setup_folders()

    elif cmd == "sp-validate":
        from agents.sharepoint_manager import cmd_validate_folders
        cmd_validate_folders()

    elif cmd == "sp-archive":
        from agents.sharepoint_manager import cmd_archive_run
        cmd_archive_run()

    elif cmd == "sp-watch":
        from agents.sharepoint_manager import cmd_archive_watch
        cmd_archive_watch()

    elif cmd == "sp-delta":
        from agents.sharepoint_manager import cmd_delta
        cmd_delta()

    elif cmd == "dc-log":
        from agents.sharepoint_manager import cmd_dc_log
        cmd_dc_log(sys.argv[2:])

    elif cmd == "dc-summary":
        from agents.sharepoint_manager import cmd_dc_summary
        cmd_dc_summary()

    elif cmd == "sp-submit-status":
        from agents.sharepoint_manager import cmd_submit_status
        cmd_submit_status()

    elif cmd == "sp-submit-process":
        from agents.sharepoint_manager import cmd_submit_process
        cmd_submit_process()

    elif cmd == "sp-submit-verify":
        from agents.sharepoint_manager import cmd_submit_verify
        dt = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_submit_verify(doc_type=dt)

    elif cmd == "sp-submit-watch":
        from agents.sharepoint_manager import cmd_submit_watch
        cmd_submit_watch()

    elif cmd == "sp-auto-rename":
        from agents.sharepoint_manager import cmd_auto_rename
        cmd_auto_rename()

    elif cmd == "sp-review-status":
        from agents.sharepoint_manager import cmd_review_status
        cmd_review_status()

    elif cmd == "sp-approve-ready":
        from agents.sharepoint_manager import cmd_approve_ready
        cmd_approve_ready()

    elif cmd == "sp-approve":
        from agents.sharepoint_manager import cmd_approve_milestone
        cmd_approve_milestone()

    elif cmd == "sp-cross-check":
        if len(sys.argv) < 3:
            print("Usage: python run.py sp-cross-check <SITE_CODE>")
            sys.exit(1)
        site = sys.argv[2]
        from agents.sharepoint_manager import SubmitAgent
        agent = SubmitAgent()
        import json
        result = agent.cross_check_cc_docs(site)
        print(json.dumps(result, indent=2))

    elif cmd == "sp-notify-ready":
        from agents.sharepoint_manager import cmd_notify_ready
        cmd_notify_ready()

    elif cmd == "sp-pending-visual":
        from agents.sharepoint_manager import cmd_pending_visual_status
        cmd_pending_visual_status()

    elif cmd == "sp-notify-pmc":
        from agents.sharepoint_manager import cmd_notify_pmc_validation
        cmd_notify_pmc_validation()

    elif cmd == "sp-visual-approve":
        from agents.sharepoint_manager import cmd_visual_approve
        cmd_visual_approve()

    elif cmd == "verify":
        from agents.database import DatabaseAgent
        from agents.verification import verify_document
        db = DatabaseAgent()
        docs = db.get_documents()
        print(f"Verifying {len(docs)} existing documents...")
        passed = failed = 0
        for d in docs:
            result = {
                "doc_type": d["doc_type"],
                "site_code": d["site_code"],
                "doc_date": d.get("doc_date"),
                "verified_name": d.get("verified_name"),
                "verified_designation": d.get("verified_designation"),
                "verified_date": d.get("verified_date"),
                "approved_name": d.get("approved_name"),
                "approved_designation": d.get("approved_designation"),
                "approved_date": d.get("approved_date"),
                "version": d.get("version"),
            }
            v = verify_document(result)
            if v.get("sitename"):
                from datetime import datetime
                v["verified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.upsert_verification(d["doc_type"], v)
            if v.get("status") == "failed":
                failed += 1
                print(f"  FAIL {d['filename']}: {v.get('issues', '')}")
            else:
                passed += 1
        summary = db.get_verification_summary()
        print(f"\nPassed: {passed}, Failed: {failed}")
        for s in summary:
            print(f"  {s['doc_type']}: {s['total']} total, {s['passed']} passed, {s['failed']} failed")

    elif cmd == "milestone-check":
        from agents.progress_sync import ProgressSyncAgent
        sync = ProgressSyncAgent()
        site = sys.argv[2] if len(sys.argv) > 2 else None
        ms = sys.argv[3] if len(sys.argv) > 3 else None
        results = sync.check_readiness(site_code=site, milestone=ms)
        if not results:
            print("No results.")
            return
        header = f"{'Site':12s} {'Milestone':10s} {'Status':12s} {'Ready?':6s} {'Missing Docs'}"
        print(header)
        print("-" * len(header))
        flags = []
        for r in results:
            ready = "OK" if r["ready"] else "MISSING"
            missing = ", ".join(r["missing_docs"]) if r["missing_docs"] else "-"
            print(f"{r['site_code']:12s} {r['milestone']:10s} {r['status']:12s} {ready:6s} {missing}")
            if r["has_completed_without_docs"]:
                flags.append(r)
        if flags:
            print(f"\n⚠ WARNING: {len(flags)} milestone(s) marked Completed but missing docs:")
            for r in flags:
                print(f"  {r['site_code']} / {r['milestone']}: missing {', '.join(r['missing_docs'])}")
        total = len(results)
        ready = sum(1 for r in results if r["ready"])
        print(f"\n{ready}/{total} milestones fully documented.")

    elif cmd == "verify-status":
        from agents.database import DatabaseAgent
        db = DatabaseAgent()
        summary = db.get_verification_summary()
        if not summary:
            print("No verification records found. Run `python run.py verify` first.")
            return
        print("Verification Summary:")
        for s in summary:
            print(f"  {s['doc_type']:12s} {s['total']:4d} total  {s['passed']:4d} passed  {s['failed']:4d} failed  {s['pending']:4d} pending")
        total = sum(s['total'] for s in summary)
        passed = sum(s['passed'] for s in summary)
        failed = sum(s['failed'] for s in summary)
        print(f"\n  {'TOTAL':12s} {total:4d} total  {passed:4d} passed  {failed:4d} failed")

    elif cmd == "db-reset":
        confirm = input("Delete ALL data and reset database? (yes/no): ")
        if confirm.strip().lower() == "yes":
            db_path = Path(__file__).parent / "reporting.db"
            if db_path.exists():
                db_path.unlink()
                print("Database deleted.")
            from agents.database import DatabaseAgent
            db = DatabaseAgent()
            db.init_schema()
            print("Schema recreated. DB is fresh.")
            print("\nDone. Run `python run.py import` to seed data.")
        else:
            print("Cancelled.")

    elif cmd == "rejected-docs-report":
        from agents.reports import generate_rejected_docs_report
        generate_rejected_docs_report()

    elif cmd == "watchdog-gui":
        from watchdog_gui import WatchdogGUI
        import tkinter as tk
        gui_root = tk.Tk()
        app = WatchdogGUI(gui_root)
        gui_root.protocol("WM_DELETE_WINDOW", app.on_close)
        gui_root.mainloop()

    elif cmd == "rename":
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
