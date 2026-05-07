Query the RAG platform audit log for recent admin actions.

Steps:
1. Get the ADMIN_SECRET_KEY: `grep ADMIN_SECRET_KEY .env | cut -d= -f2`
2. Fetch recent audit events:
   `curl -s -H "X-Admin-Key: <key>" "http://localhost:8000/admin/audit?limit=20"`
3. If the user asks for a specific org, add `&org_id=<id>` to the request

Display results as a table: time, action (color-coded in output), resource, resource_id, user_email, org_id, IP.

Action colour legend: delete=🔴, create=🟢, sync=🔵, update=🟡, other=⚪

If the audit table doesn't exist yet, remind the user to run `rag-migrate` to apply `006_audit_log.sql`.

Useful filters to offer:
- By action: `?action=delete`
- By org: `?org_id=N`
- Pagination: `?limit=50&offset=50`
