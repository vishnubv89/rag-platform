Ingest a document into the RAG platform knowledge base.

Ask the user for:
1. The file path or text content to ingest
2. The org_id to ingest into (list available orgs by calling `curl -s -H "X-Admin-Key: $(grep ADMIN_SECRET_KEY .env | cut -d= -f2)" http://localhost:8000/admin/orgs` if not provided)

Then:
- If a file path: read the file, POST it to `http://localhost:8000/ingest` as multipart/form-data with the org_id
- If raw text: POST to `http://localhost:8000/ingest` as JSON `{"text": "...", "org_id": N}`

Use the ADMIN_SECRET_KEY from `.env` in the `X-Admin-Key` header.

Watch for common errors:
- 422 → check org_id is a valid integer
- 500 with "CharacterNotInRepertoire" → null bytes in content; strip `\x00` before retrying
- Gemini 429 → wait 30s and retry (batch limit is 100 chunks)

Report: number of chunks created, embedding model used, and time taken.
