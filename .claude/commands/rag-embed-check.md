Verify the embedding model configuration and test that embeddings are working.

Steps:
1. Check current model in DB:
   `docker compose exec postgres psql -U rag -d rag_db -c "SELECT key, value FROM settings WHERE key='embedding_model';"`
2. Check config default in code:
   `grep embedding_model backend/src/rag_chatbot/config.py`
3. Test a live embedding call via the backend:
   `curl -s -H "X-Admin-Key: $(grep ADMIN_SECRET_KEY .env | cut -d= -f2)" -X POST http://localhost:8000/admin/test-embed -H "Content-Type: application/json" -d '{"text":"hello world"}'`
   (If this endpoint doesn't exist, skip step 3)

Valid Gemini embedding models (as of 2026):
- `models/gemini-embedding-2` ← current default, recommended
- `models/gemini-embedding-001` ← older, still valid
- `models/gemini-embedding-2-preview` ← preview tier

Invalid: `models/gemini-embedding-002` (does not exist — causes 404 from Gemini API).

Batch limits: max 100 texts per embed_batch call. Larger documents are split into ≤100-chunk sub-batches with 0.5s pause between batches and exponential backoff on 429.

Report: current model, whether it matches the code default, and embedding test result.
