Apply any pending database migrations to the RAG platform.

Steps:
1. List migration files: `ls backend/src/rag_chatbot/db/migrations/*.sql | sort`
2. Check which have already been applied by querying the DB:
   `docker compose exec postgres psql -U rag -d rag_db -c "SELECT name FROM schema_migrations ORDER BY name;" 2>/dev/null`
   (If schema_migrations doesn't exist, all migrations may need applying)
3. For each unapplied migration, apply it:
   `docker compose exec -T postgres psql -U rag -d rag_db < backend/src/rag_chatbot/db/migrations/<file>.sql`
4. Confirm by re-querying applied migrations

Migration naming convention: `NNN_description.sql` (e.g. `001_initial.sql`, `006_audit_log.sql`).

If the backend container is running, restart it after migrations so models are refreshed:
`docker compose restart backend`

Report which migrations were applied, which were already present, and any errors.
