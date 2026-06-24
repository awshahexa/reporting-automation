"""DatabaseAgent — SQLite schema + CRUD for the entire system."""
import sqlite3
from datetime import datetime
from pathlib import Path


class DatabaseAgent:
    def __init__(self, db_path=None):
        self.db_path = db_path or (Path(__file__).parent.parent / "reporting.db")
        self.init_schema()

    def connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_schema(self):
        conn = self.connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_code TEXT UNIQUE NOT NULL,
                site_name TEXT,
                region TEXT,
                du_code TEXT,
                du_name TEXT,
                node_type TEXT,
                equipment_model TEXT,
                equipment_function TEXT,
                latitude TEXT,
                longitude TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS site_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_code TEXT NOT NULL,
                node_type TEXT NOT NULL,
                activity_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(site_code, node_type, activity_name, field_name)
            );

            CREATE TABLE IF NOT EXISTS milestone_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_code TEXT NOT NULL,
                milestone TEXT NOT NULL,
                status TEXT DEFAULT 'Not started',
                actual_date TEXT,
                updated_by TEXT DEFAULT 'system',
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(site_code, milestone)
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_code TEXT,
                doc_type TEXT,
                milestone TEXT,
                filename TEXT,
                filepath TEXT,
                version TEXT,
                date_uploaded TEXT,
                date_extracted TEXT,
                doc_date TEXT,
                verified_name TEXT,
                verified_designation TEXT,
                verified_date TEXT,
                approved_name TEXT,
                approved_designation TEXT,
                approved_date TEXT,
                raw_text TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS document_types (
                code TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                extraction_template TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                site_code TEXT,
                document_id INTEGER,
                milestone TEXT,
                old_status TEXT,
                new_status TEXT,
                detail TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tracker_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_code TEXT,
                node_type TEXT,
                activity_name TEXT,
                field_name TEXT,
                old_value TEXT,
                new_value TEXT,
                changed_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_code TEXT,
                milestone TEXT,
                notification_type TEXT,
                status TEXT DEFAULT 'pending',
                details TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                sent_at TEXT
            );

            CREATE TABLE IF NOT EXISTS dc_archive_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                doc_type TEXT,
                source_folder TEXT,
                source_path TEXT,
                archive_path TEXT,
                file_size INTEGER,
                author TEXT,
                file_last_modified TEXT,
                archived_at TEXT DEFAULT (datetime('now')),
                archived_by TEXT,
                checksum TEXT,
                status TEXT,
                notes TEXT
            );
        """)
        self._init_verification_schema(conn)
        conn.commit()
        conn.close()

    def _init_verification_schema(self, conn):
        tables = {
            "verification_po": """
                sitename TEXT PRIMARY KEY, po_number TEXT, vendor TEXT, total_amount TEXT,
                doc_date TEXT, verified_name TEXT, verified_date TEXT,
                approved_name TEXT, approved_date TEXT,
                date_valid INTEGER, signatory_valid INTEGER, ref_number_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_dn": """
                sitename TEXT PRIMARY KEY, dn_number TEXT, doc_date TEXT, delivery_date TEXT,
                vendor TEXT, customer TEXT, site_name TEXT, item_description TEXT,
                date_valid INTEGER, signatory_valid INTEGER, ref_number_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_bl": """
                sitename TEXT PRIMARY KEY, bl_number TEXT, doc_date TEXT,
                shipper TEXT, consignee TEXT, vessel TEXT, port_loading TEXT, port_discharge TEXT,
                date_valid INTEGER, ref_number_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_pl": """
                sitename TEXT PRIMARY KEY, pl_number TEXT, doc_date TEXT,
                vendor TEXT, consignee TEXT, project TEXT, reference TEXT, po_number TEXT,
                prepared_by TEXT, date_prepared TEXT, total_quantity TEXT,
                item_description TEXT, quantity TEXT, weight TEXT,
                date_valid INTEGER, ref_number_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_tssr": """
                sitename TEXT PRIMARY KEY, site_code TEXT, region TEXT, site_structure TEXT,
                equipment_model TEXT, equipment_function TEXT, latitude TEXT, longitude TEXT,
                verified_name TEXT, verified_designation TEXT, verified_date TEXT,
                approved_name TEXT, approved_designation TEXT, approved_date TEXT,
                date_valid INTEGER, signatory_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_satp": """
                sitename TEXT PRIMARY KEY, site_code TEXT, doc_date TEXT, test_result TEXT,
                verified_name TEXT, verified_date TEXT, approved_name TEXT, approved_date TEXT,
                date_valid INTEGER, signatory_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_mop": """
                sitename TEXT PRIMARY KEY, scope TEXT, node_type TEXT,
                prepared_by TEXT, prepared_date TEXT, reviewed_by TEXT, reviewed_date TEXT,
                approved_by TEXT, approved_date TEXT, equipment_model TEXT, software_version TEXT,
                related_ne TEXT, date_valid INTEGER, signatory_valid INTEGER, ref_number_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_smr": """
                sitename TEXT PRIMARY KEY, smr_number TEXT, doc_date TEXT,
                verified_name TEXT, verified_date TEXT, reviewed_name TEXT, reviewed_date TEXT,
                approved_name TEXT, approved_date TEXT, migration_status TEXT, migration_result TEXT,
                date_valid INTEGER, signatory_valid INTEGER, ref_number_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_cc": """
                sitename TEXT PRIMARY KEY, doc_date TEXT,
                verified_name TEXT, verified_date TEXT, approved_name TEXT, approved_date TEXT,
                accepted_name TEXT, accepted_date TEXT,
                date_valid INTEGER, signatory_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_ft": """
                sitename TEXT PRIMARY KEY, doc_date TEXT,
                date_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_claim_form": """
                sitename TEXT PRIMARY KEY, doc_date TEXT,
                date_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_paf": """
                sitename TEXT PRIMARY KEY, paf_number TEXT, doc_date TEXT,
                verified_name TEXT, verified_date TEXT, approved_name TEXT, approved_date TEXT,
                date_valid INTEGER, signatory_valid INTEGER, ref_number_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
            "verification_faf": """
                sitename TEXT PRIMARY KEY, faf_number TEXT, doc_date TEXT,
                verified_name TEXT, verified_date TEXT, approved_name TEXT, approved_date TEXT,
                date_valid INTEGER, signatory_valid INTEGER, ref_number_valid INTEGER,
                issues TEXT, status TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
            """,
        }
        for name, schema in tables.items():
            conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({schema})")

    # ── Sites ──

    def get_all_sites(self):
        conn = self.connect()
        rows = conn.execute("SELECT * FROM sites ORDER BY site_code").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_site(self, site_code):
        conn = self.connect()
        row = conn.execute("SELECT * FROM sites WHERE site_code=?", (site_code,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def upsert_site(self, site_code, **kwargs):
        conn = self.connect()
        fields = ["site_code"] + list(kwargs.keys())
        placeholders = ["?"] * len(fields)
        values = [site_code] + list(kwargs.values())
        updates = ", ".join(f"{k}=excluded.{k}" for k in kwargs)
        conn.execute(f"""
            INSERT INTO sites ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT(site_code) DO UPDATE SET
                {updates}, updated_at=datetime('now')
        """, values)
        conn.commit()
        conn.close()

    # ── Site Activities ──

    def get_activities(self, site_code, node_type=None):
        conn = self.connect()
        if node_type:
            rows = conn.execute(
                "SELECT * FROM site_activities WHERE site_code=? AND node_type=? ORDER BY activity_name, field_name",
                (site_code, node_type)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM site_activities WHERE site_code=? ORDER BY node_type, activity_name, field_name",
                (site_code,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def upsert_activity(self, site_code, node_type, activity_name, field_name, value):
        conn = self.connect()
        conn.execute("""
            INSERT INTO site_activities (site_code, node_type, activity_name, field_name, value, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(site_code, node_type, activity_name, field_name) DO UPDATE SET
                value=excluded.value, updated_at=datetime('now')
        """, (site_code, node_type, activity_name, field_name, value))
        conn.commit()
        conn.close()

    def get_activity_value(self, site_code, activity_name, field_name, node_type=None):
        conn = self.connect()
        if node_type:
            row = conn.execute(
                "SELECT value FROM site_activities WHERE site_code=? AND node_type=? AND activity_name=? AND field_name=?",
                (site_code, node_type, activity_name, field_name)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT value FROM site_activities WHERE site_code=? AND activity_name=? AND field_name=?",
                (site_code, activity_name, field_name)
            ).fetchone()
        conn.close()
        return row["value"] if row else None

    # ── Milestone Status ──

    def get_milestone_status(self, site_code=None, milestone=None):
        conn = self.connect()
        query = "SELECT * FROM milestone_status WHERE 1=1"
        params = []
        if site_code:
            query += " AND site_code=?"
            params.append(site_code)
        if milestone:
            query += " AND milestone=?"
            params.append(milestone)
        query += " ORDER BY site_code, milestone"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def upsert_milestone_status(self, site_code, milestone, status, actual_date=None, updated_by="system"):
        conn = self.connect()
        conn.execute("""
            INSERT INTO milestone_status (site_code, milestone, status, actual_date, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(site_code, milestone) DO UPDATE SET
                status=excluded.status, actual_date=excluded.actual_date,
                updated_by=excluded.updated_by, updated_at=datetime('now')
        """, (site_code, milestone, status, actual_date, updated_by))
        conn.commit()
        conn.close()

    # ── Documents ──

    def get_documents(self, site_code=None, doc_type=None, limit=1000):
        conn = self.connect()
        query = "SELECT * FROM documents WHERE 1=1"
        params = []
        if site_code:
            query += " AND site_code=?"
            params.append(site_code)
        if doc_type:
            query += " AND doc_type=?"
            params.append(doc_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def upsert_document(self, site_code, doc_type, filename, **kwargs):
        conn = self.connect()
        fields = ["site_code", "doc_type", "filename"] + list(kwargs.keys())
        placeholders = ["?"] * len(fields)
        values = [site_code, doc_type, filename] + list(kwargs.values())
        updates = ", ".join(f"{k}=excluded.{k}" for k in kwargs)
        conn.execute(f"""
            INSERT INTO documents ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT DO NOTHING
        """, values)
        conn.commit()
        conn.close()

    # ── Verification ──

    def upsert_verification(self, doc_type, data):
        table = f"verification_{doc_type.lower().replace('-','_')}"
        conn = self.connect()
        cols = list(data.keys())
        placeholders = ["?"] * len(cols)
        values = [data.get(k) for k in cols]
        updates = ", ".join(f"{k}=excluded.{k}" for k in cols if k != "sitename")
        try:
            conn.execute(f"""
                INSERT INTO {table} ({', '.join(cols)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT(sitename) DO UPDATE SET
                    {updates}, updated_at=datetime('now')
            """, values)
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"  DB upsert_verification error ({doc_type}): {e}")
        conn.close()

    def get_verification(self, doc_type, site_code):
        table = f"verification_{doc_type.lower().replace('-','_')}"
        conn = self.connect()
        row = conn.execute(f"SELECT * FROM {table} WHERE sitename=?", (site_code,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_verifications(self, doc_type=None, status=None, limit=500):
        conn = self.connect()
        results = []
        tables = ["po", "dn", "bl", "pl", "tssr", "satp", "mop", "smr", "cc", "ft", "claim_form", "paf", "faf"]
        for dt in tables:
            if doc_type and dt != doc_type.lower():
                continue
            query = f"SELECT * FROM verification_{dt}"
            params = []
            if status:
                query += " WHERE status=?"
                params.append(status)
            query += " ORDER BY verified_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                d = dict(r)
                d["doc_type"] = dt
                results.append(d)
        conn.close()
        return results

    def get_verification_summary(self):
        conn = self.connect()
        tables = ["po", "dn", "bl", "pl", "tssr", "satp", "mop", "smr", "cc", "ft", "claim_form", "paf", "faf"]
        results = []
        for dt in tables:
            row = conn.execute(f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='passed' THEN 1 ELSE 0 END) as passed,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status IS NULL OR status='' THEN 1 ELSE 0 END) as pending
                FROM verification_{dt}
            """).fetchone()
            results.append({
                "doc_type": dt.upper(),
                "total": row["total"],
                "passed": row["passed"] or 0,
                "failed": row["failed"] or 0,
                "pending": row["pending"] or 0,
            })
        conn.close()
        return results

    def get_verification_checklist(self, milestone_filter=None, search="", limit=200):
        """Get per-site document verification checklist.
        Returns list of dicts: {site_code, node_type, milestone, docs: {doc_type: {status, issues}}}
        """
        conn = self.connect()

        # Single UNION ALL query for all verification tables
        all_doc_types = ["po", "dn", "bl", "pl", "tssr", "satp", "mop", "smr", "cc", "ft", "paf", "faf"]
        union_parts = []
        for dt in all_doc_types:
            union_parts.append(f"SELECT '{dt}' as doc_type, sitename, status, issues FROM verification_{dt}")
        verif_sql = " UNION ALL ".join(union_parts)
        verif_rows = conn.execute(verif_sql).fetchall()
        verif_by_site = {}
        for r in verif_rows:
            verif_by_site[(r["sitename"], r["doc_type"])] = {"status": r["status"], "issues": r["issues"]}

        # Milestone status
        ms_rows = conn.execute("SELECT site_code, milestone, status FROM milestone_status").fetchall()
        ms_by_site = {}
        for r in ms_rows:
            ms_by_site.setdefault(r["site_code"], {})[r["milestone"]] = r["status"]

        # Apply milestone filter + search in SQL when possible
        site_rows = conn.execute("SELECT site_code, node_type FROM sites ORDER BY site_code").fetchall()
        conn.close()

        result = []
        for s in site_rows:
            sc = s["site_code"]
            if search and search not in sc.upper():
                continue

            site_ms = ms_by_site.get(sc, {})
            achieved = "Not started"
            for ml in ["FAC", "PAC", "CC"]:
                if site_ms.get(ml) == "Completed":
                    achieved = ml
                    break
            if milestone_filter and achieved != milestone_filter:
                continue

            docs = {}
            for dt in all_doc_types:
                v = verif_by_site.get((sc, dt))
                docs[dt.upper()] = {"status": (v["status"] if v else None), "issues": (v["issues"] if v else None)}

            result.append({
                "site_code": sc,
                "node_type": s["node_type"],
                "milestone": achieved,
                "docs": docs,
            })

            if len(result) >= limit:
                break

        return result

    def get_audit_log(self, site_code=None, milestone=None, limit=200):
        conn = self.connect()
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if site_code:
            query += " AND site_code=?"
            params.append(site_code)
        if milestone:
            query += " AND milestone=?"
            params.append(milestone)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def log_audit_event(self, event_type, site_code, document_id=None, milestone=None, old_status=None, new_status=None, detail=None):
        conn = self.connect()
        conn.execute("""
            INSERT INTO audit_log (event_type, site_code, document_id, milestone, old_status, new_status, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (event_type, site_code, document_id, milestone, old_status, new_status, detail))
        conn.commit()
        conn.close()

    # ── Tracker Audit ──

    def log_tracker_change(self, site_code, node_type, activity_name, field_name, old_value, new_value):
        conn = self.connect()
        conn.execute("""
            INSERT INTO tracker_audit (site_code, node_type, activity_name, field_name, old_value, new_value, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (site_code, node_type, activity_name, field_name, str(old_value), str(new_value)))
        conn.commit()
        conn.close()

    def get_tracker_audit(self, site_code=None, limit=100):
        conn = self.connect()
        query = "SELECT * FROM tracker_audit"
        params = []
        if site_code:
            query += " WHERE site_code=?"
            params.append(site_code)
        query += " ORDER BY changed_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_unauthorized_date_changes(self, limit=100):
        conn = self.connect()
        rows = conn.execute("""
            SELECT * FROM tracker_audit
            WHERE field_name LIKE '%date%' OR field_name LIKE '%actual%'
            ORDER BY changed_at DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_date_changes_summary(self):
        conn = self.connect()
        rows = conn.execute("""
            SELECT field_name, COUNT(*) as cnt,
                   SUM(CASE WHEN old_value IS NULL OR old_value='' THEN 1 ELSE 0 END) as new_entries,
                   SUM(CASE WHEN old_value IS NOT NULL AND old_value!='' THEN 1 ELSE 0 END) as overwrites
            FROM tracker_audit
            WHERE field_name LIKE '%date%' OR field_name LIKE '%actual%'
            GROUP BY field_name
            ORDER BY cnt DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Notifications ──

    def upsert_notification(self, site_code, milestone, details="", notification_type="ready_for_review"):
        conn = self.connect()
        conn.execute("""
            INSERT INTO notifications (site_code, milestone, notification_type, status, details, created_at)
            VALUES (?, ?, ?, 'pending', ?, datetime('now'))
        """, (site_code, milestone, notification_type, details))
        conn.commit()
        conn.close()

    def mark_notification_sent(self, notification_id):
        conn = self.connect()
        conn.execute("UPDATE notifications SET status='sent', sent_at=datetime('now') WHERE id=?", (notification_id,))
        conn.commit()
        conn.close()

    def get_notifications(self, site_code=None, limit=50):
        conn = self.connect()
        query = "SELECT * FROM notifications"
        params = []
        if site_code:
            query += " WHERE site_code=?"
            params.append(site_code)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── DC Archive ──

    def log_archive(self, **kwargs):
        conn = self.connect()
        cols = list(kwargs.keys())
        vals = [kwargs[k] for k in cols]
        conn.execute(f"""
            INSERT INTO dc_archive_log ({', '.join(cols)})
            VALUES ({', '.join(['?'] * len(vals))})
        """, vals)
        conn.commit()
        conn.close()

    def get_archive_log(self, limit=50):
        conn = self.connect()
        rows = conn.execute("SELECT * FROM dc_archive_log ORDER BY archived_at DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Summary ──

    def get_summary_stats(self):
        conn = self.connect()
        total_sites = conn.execute("SELECT COUNT(*) as c FROM sites").fetchone()["c"]
        total_documents = conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()["c"]
        ms_rows = conn.execute("""
            SELECT milestone, status, COUNT(*) as cnt
            FROM milestone_status GROUP BY milestone, status
        """).fetchall()
        conn.close()
        return {
            "total_sites": total_sites,
            "total_documents": total_documents,
            "milestone_status": [dict(r) for r in ms_rows],
        }

    def export_full_report(self):
        conn = self.connect()
        rows = conn.execute("""
            SELECT s.site_code, s.site_name, s.node_type,
                   ms.milestone, ms.status, ms.actual_date
            FROM sites s
            LEFT JOIN milestone_status ms ON ms.site_code = s.site_code
            ORDER BY s.site_code, ms.milestone
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Cleanup ──

    def clear_all_data(self):
        conn = self.connect()
        for table in ["tracker_audit", "audit_log", "notifications", "documents", "milestone_status", "site_activities"]:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
        conn.close()
