"""Seed the reporting DB from existing TSSR data and tracker Excel files."""
import sys, sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agents.database import DatabaseAgent
from agents.config import DB_PATH, MILESTONES, MILESTONE_DOCS


def seed_from_tssr(tssr_db_path):
    """Copy sites from existing TSSR SQLite database."""
    tssr_path = Path(tssr_db_path)
    if not tssr_path.exists():
        print(f"TSSR DB not found at {tssr_path}")
        return

    db = DatabaseAgent()
    conn = sqlite3.connect(str(tssr_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM tssr").fetchall()
    count = 0
    for row in rows:
        site_code = row["Site_Code"] or row["Site_Name"]
        if not site_code:
            continue
        db.upsert_site(
            site_code=site_code,
            site_name=row["Site_Name"] or site_code,
            region=row["Region"],
            equipment_model=row["Equipment_Model"],
            equipment_function=row["Equipment_Function"],
            latitude=row["Latitude"],
            longitude=row["Longitude"]
        )
        count += 1

    print(f"Seeded {count} sites from TSSR database")

    photos_dir = Path(__file__).parent / "photos"
    if photos_dir.exists():
        for site_dir in photos_dir.iterdir():
            if site_dir.is_dir():
                db.log_event("seed", site_code=site_dir.name,
                             detail=f"Photos exist for {site_dir.name}")
    conn.close()


def create_milestones():
    """Initialize milestone_status for all known sites."""
    db = DatabaseAgent()
    sites = db.get_all_sites()
    for s in sites:
        for ms in MILESTONES:
            db.set_milestone_status(s["site_code"], ms, "Not started", updated_by="seed")
    print(f"Initialized milestones for {len(sites)} sites")


if __name__ == "__main__":
    tssr_path = Path(__file__).parent.parent / "TSSR-Extractor" / "tssr_data.db"
    seed_from_tssr(tssr_path)
    create_milestones()

    db = DatabaseAgent()
    stats = db.get_summary_stats()
    print(f"\nFinal state:")
    print(f"  Sites: {stats['total_sites']}")
    print(f"  Documents: {stats['total_documents']}")
