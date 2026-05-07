Rebuild and restart one or more RAG platform services.

Ask the user which service(s) to rebuild if not specified. Valid services: `backend`, `frontend`, `admin-ui`, `all`.

For each service:
1. `docker compose build <service> --no-cache` — always use --no-cache to avoid stale layers
2. `docker compose up -d <service>` — restart with the new image
3. Wait for the healthcheck to pass: poll `docker compose ps <service>` until Status shows "healthy" (max 60s)
4. Tail recent logs: `docker compose logs <service> --tail=20`

For `all`: rebuild in dependency order — postgres (skip, no build), backend, then frontend + admin-ui in parallel.

Common reasons to rebuild:
- New Python dependency added to pyproject.toml → rebuild backend
- Frontend env vars changed (VITE_API_BASE_URL, VITE_ADMIN_KEY) → rebuild frontend
- Admin UI template changes aren't hot-reloaded → rebuild admin-ui

Report: build time per service, final health status, and any startup errors from logs.
