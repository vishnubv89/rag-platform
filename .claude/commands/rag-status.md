Check the health of all RAG platform services and report their status.

Run the following and summarise the results clearly:

1. `docker compose ps` — show running containers and their state
2. `docker compose logs backend --tail=20` — check for recent errors
3. `docker compose logs backup --tail=5` — confirm last backup completed
4. `curl -s http://localhost:8000/health` — hit the backend health endpoint

Report a table: service name, status (✅ healthy / ⚠️ degraded / ❌ down), and any notable log lines. If anything is down, suggest the likely fix based on what you know about this project.
