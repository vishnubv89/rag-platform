Tail and analyse logs from RAG platform services.

If the user specifies a service (backend / frontend / admin-ui / postgres / backup), show logs for that service.
If not specified, show backend logs by default.

Commands:
- Recent errors: `docker compose logs <service> --tail=100 | grep -iE "error|exception|traceback|500|422"`
- Full recent: `docker compose logs <service> --tail=50`
- Follow live: suggest `docker compose logs -f <service>` (tell the user to run it themselves in a terminal)

Interpret common error patterns based on project knowledge:
- `CharacterNotInRepertoire` → null bytes in ingested text; fix is `_sanitize()` in loader.py
- `asyncpg.exceptions` → DB connection or schema issue; check postgres health
- `RateLimitExceeded` → normal if user is hitting /chat or /suggest too fast
- `422 Unprocessable Entity` → form field type mismatch; check if org_id is empty string vs int
- `405 Method Not Allowed` → nginx not proxying the route; check nginx.conf location blocks
- `embed_batch` 429 → Gemini quota; batching is in chunks of 100 with retry backoff

Summarise: total error count in last 100 lines, most frequent error type, suggested fix if known.
