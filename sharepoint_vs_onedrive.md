# SharePoint vs OneDrive Architecture Options

## Scenario 1: Hot folders in SharePoint, rest in OneDrive

**Problems:**
- **Pipeline breaks across platforms** — Submit → Review → Approve → Archive requires moving files between SharePoint and OneDrive via Graph API. Two different `driveId`s, different permission scopes, more complex auth tokens.
- **Review/Approve need team access** — OneDrive is personal. PMC, PMO, and reviewers cannot access docs staged in your OneDrive unless every folder is shared individually.
- **Watchdog complexity** — Hot folder listener would need to watch SharePoint (webhook or polling), then subsequent moves within OneDrive still need their own watcher.

**Verdict:** Not recommended unless the hot folder is the only place multiple people submit files, and you personally handle the rest.

---

## Scenario 2: Working folder in SharePoint, archive in OneDrive

**Better, but still suboptimal:**
- **Active pipeline stays together** — Submit → Review → Approve all in SharePoint. Team collaboration works, permission inheritance is clean, and triggers cover the whole workflow.
- **Archive cross-platform** — Only the final Approve → Archive step crosses to OneDrive. Single download-from-SharePoint → upload-to-OneDrive operation, manageable.
- **OneDrive archive is personal** — If you leave or the OneDrive account changes, the archive goes with it. Discovery by others is poor.

**Verdict:** Workable if archive is truly personal cold storage, but SharePoint archive is preferred for organizational retention.

---

## Scenario 3: Everything in OneDrive for Business

**Pros:**
- Same Graph API surface as SharePoint (`me/drive/root:/path` or `drives/{id}`) — code changes minimally
- Hot folder works naturally — others can share-edit specific folders
- Watchdog/webhooks supported via Graph API subscriptions
- No cross-platform moves (everything under one `driveId`)
- Faster initial setup (no site collection provisioning)

**Cons:**
- **Single point of failure** — tied to one person's account. If that user leaves, access breaks unless an admin takes ownership.
- **Permission management is flat** — no SharePoint groups, no inheritance-based security. Every shared folder is a manual sharing link. Harder to control "PMC can see Approve but not Review".
- **Storage quota** — typically 1–5 TB vs SharePoint's 25 TB+. 953 sites × 3 milestones × multiple PDFs adds up.
- **No site-level backup/retention policies** — SharePoint document libraries support versioning, retention labels, and legal hold; OneDrive is more limited.
- **Not suited for >5 users** — sharing friction grows linearly.

**Verdict:** Works fine for a single-user or 2–3 person pilot. If it needs to survive team turnover or scale beyond a handful of users, use a SharePoint team site document library instead.

---

## Recommendation

**All in SharePoint** is the simplest and most correct architecture:
- Single `driveId` for all Graph API calls
- Permission inheritance (Working folder → subfolders inherit)
- Power Automate can watch the whole tree
- Archive can go to a separate SharePoint document library (e.g., "Archive") on the same site with restricted access
- No cross-platform file moves = less code, fewer failure modes

If constrained by **SharePoint storage limits**, archive to a secondary SharePoint site (not OneDrive) — same API surface, team-accessible, no cross-platform complexity.

---

*Analysis date: 2026-06-18*
