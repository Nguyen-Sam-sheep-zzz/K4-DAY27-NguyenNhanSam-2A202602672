<!-- Preview only; never posted. PR head: 501f95e016f9cd241cb1a7dd60b9a27102bcb413 -->

### Automated review (confidence 52%)

Adds login and cloud-push commands, token helpers, a user_id task column, and a sync request. The changes also alter task insertion and introduce client-side authentication and data-isolation behavior that need correction and clarification.

- **[blocker]** `tasktrack/storage.py:26` — This interpolates `title` directly into SQL, so a title containing a quote can break the insert, and crafted input can alter the query. Keep parameterized SQL here: `INSERT INTO tasks (title, user_id) VALUES (?, ?)` with `(title, user_id)`.
- **[issue]** `tasktrack/storage.py:15` — Adding this column to `CREATE TABLE IF NOT EXISTS` does not update databases that already have a `tasks` table. On those installs, the new insert references a nonexistent `user_id` column and fails. Please add a schema migration (and define how existing tasks are assigned) before relying on this column.
- **[issue]** `tasktrack/sync.py:12` — This sends the bearer token over plain HTTP, where it can be observed or modified in transit. Use HTTPS and ensure the endpoint's certificate is verified before transmitting credentials or task data.
- **[issue]** `tasktrack/auth.py:10` — This is a fast, unsalted MD5 password hash, and `issue_token` derives a repeatable token locally rather than authenticating with a server. Passwords are vulnerable to offline guessing, and the client has no basis to know whether credentials are valid. Please use a server-authenticated login/token flow and an appropriate password-hashing scheme on the server; avoid treating this locally generated value as a credential.
- **[issue]** `tasktrack/sync.py:20` — `_current_user_id()` returns 1 for every task, regardless of the logged-in user or the `user_id` stored on the task. This can associate unrelated users' tasks with the same account on the server. Derive identity from a validated session and define how local tasks are assigned to that user; do not hard-code it.
