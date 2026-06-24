# SharePoint Integration — Security Q&A for Management

---

## Q: Will the Client Secret expose Sacofa's confidential documents or data?

**A: No.** A Client Secret is an app password — it does **not** contain, reveal, or decrypt any Sacofa data. It only proves the application's identity.

What the application can access depends entirely on the **permissions you grant** during Azure App registration. These are explicit, scoped, and fully controlled by Sacofa IT.

### Analogy
Think of the Client Secret like a building access card:
- The card itself contains no files or information
- It only lets the holder enter the doors you specify
- You decide which floors and rooms the card can access

### What we can restrict (examples)

| Setting | What It Controls |
|---------|-----------------|
| **Permission scope** | Read-only vs read-write to the specific SharePoint site |
| **Site/Drive scope** | Limit access to a single site (e.g., `Sites.ReadWrite.All` for the `Sites Document` library only) |
| **Secret rotation** | Sacofa IT sets expiry (e.g., 6 months / 1 year) |
| **IP restrictions** | (Optional) Only accept API calls from whitelisted office IPs |

### Our recommendation to Sacofa IT
Request the **minimum** permissions needed for the pipeline to function:

1. **SharePoint** — `Sites.ReadWrite.All` scoped to the specific `Sites Document` site (not all SharePoint sites)
2. **OneDrive Archive** — `Files.ReadWrite.All` scoped to the archive drive (if archived to OneDrive)
3. **No user impersonation** — Use **application permissions** (app-only), not delegated permissions (no user login required)
4. **Secret rotation** — Set 6-month or 1-year expiry with a reminder to renew

### What we do to protect the secret
- Stored in an environment variable, **never** committed to git or source code
- Only stored on the local server running the automation
- Our codebase references it via `os.getenv("SHAREPOINT_CLIENT_SECRET")` — no hardcoded values

---

## Q: Can someone with the secret access employee emails or personal files?

**A: No.** The app only has access to what the permissions specifically grant. If we only request `Sites.ReadWrite.All` for a specific SharePoint document library, the app cannot read user mailboxes, OneDrive personal files, Teams chats, or any other Microsoft 365 service.

---

## Q: What happens if the secret expires or is revoked?

**A:** The automation stops working — documents will queue up in the local hot folder and won't be synced until a new secret is provided. No data is lost or corrupted. A warning log entry captures the authentication failure.

---

## Summary
The Client Secret is a **technical credential for the app**, not a key to Sacofa's data. Sacofa IT maintains full control over what the app can do through configurable Azure permissions.
