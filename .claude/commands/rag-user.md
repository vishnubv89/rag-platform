Manage users in the RAG platform via the admin API.

Ask the user what they want to do:
1. **List users** — `GET /admin/users?org_id=<id>&limit=20`
2. **Create user** — ask for email, password, role (member/admin/superadmin), org_id; POST to `/admin/users`
3. **Toggle active/inactive** — ask for user_id; POST to `/admin/users/<id>/toggle`
4. **Delete user** — ask for user_id and confirm; DELETE `/admin/users/<id>`

Always read ADMIN_SECRET_KEY from `.env`:
`grep ADMIN_SECRET_KEY .env | cut -d= -f2`

Use it as `X-Admin-Key` header on all requests.

Base URL: `http://localhost:8000`

Role hierarchy: superadmin > admin > member. Superadmins see all orgs; members are locked to their assigned org_id.

Known quirk: org_id must be a valid integer — never send an empty string or you'll get a 422.

Report the result of the operation and the user's final state.
