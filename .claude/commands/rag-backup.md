Trigger an immediate database backup and verify it succeeded.

Steps:
1. Check if the backup container is running: `docker compose ps backup`
2. If running, exec a manual backup: `docker compose exec backup sh /backup.sh`
3. If not running: `docker compose up -d backup` then wait 5s and check logs
4. Verify: `docker compose logs backup --tail=10` — look for "[backup] dump complete"
5. List backup files: `docker compose exec backup ls -lh /backups/`

Report: backup file name, size, timestamp, and how many old backups exist.

Known issue: the pgvector image has no crontab — the service uses a sleep loop. If you see "crontab: not found" in logs, the container is using an old entrypoint; force-recreate it with `docker compose up -d --force-recreate backup`.
