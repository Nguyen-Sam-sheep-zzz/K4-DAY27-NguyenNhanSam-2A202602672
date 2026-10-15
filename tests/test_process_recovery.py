import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ProcessRecoveryTests(unittest.TestCase):
    def test_three_processes_pause_resume_then_restore_without_duplicate_post(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "process.db")
            rows = []
            for stage in ["start", "approve", "inspect"]:
                process = subprocess.run(
                    [sys.executable, "-X", "utf8", "-m", "tests.resume_worker", path, "process-thread", stage],
                    cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8", timeout=35,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                rows.append(json.loads(process.stdout))
            self.assertTrue(rows[0]["interrupted"])
            self.assertEqual(rows[0]["post_attempts"], 0)
            self.assertEqual(rows[1]["final_action"], "committed")
            self.assertEqual(rows[1]["post_attempts"], 1)
            self.assertEqual(rows[2]["final_action"], "committed")
            self.assertEqual(rows[2]["post_attempts"], 0)
            self.assertEqual(sum(r["fetches"] for r in rows), 1)
            self.assertEqual(sum(r["analyses"] for r in rows), 1)


if __name__ == "__main__":
    unittest.main()
