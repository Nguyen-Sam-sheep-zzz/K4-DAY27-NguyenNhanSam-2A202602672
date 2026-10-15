<!-- Preview only; never posted. PR head: 164615656d47c67b0857daf02fcd412c55333d5d -->

### Automated review (confidence 79%)

Adds a priority field to tasks, accepts priority on the CLI, stores it in SQLite, and displays and sorts tasks by priority. The schema initialization only creates the new column for fresh databases; it does not migrate existing task databases.

- **[issue]** `tasktrack/storage.py:?` — `CREATE TABLE IF NOT EXISTS` does not add `priority` to an existing `tasks` table. After upgrading with a database created by the previous version, `add()` and `list()` will fail with `sqlite3.OperationalError: no such column: priority`. Add a migration (for example, inspect the table and `ALTER TABLE ... ADD COLUMN priority INTEGER NOT NULL DEFAULT 0`) so existing tasks remain usable.
- **[suggestion]** `tasktrack/cli.py:?` — The help text defines priorities as 0, 1, or 2, but `type=int` accepts other values. Those values are stored and displayed as `?`, and can affect ordering. Restrict the argument to the supported levels (for example, with `choices=(0, 1, 2)`) or validate it in storage if callers besides the CLI can supply priorities.
