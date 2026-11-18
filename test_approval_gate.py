import os
import tempfile
import unittest
from approval_gate import (
    GateError, connect, decide_job, list_audit, list_jobs,
    queue_job, run_next_approved,
)


class ApprovalGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = connect(os.path.join(self.tmp.name, "test.db"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_requires_approval(self):
        job = queue_job(self.db, "count_records", ["A", "B"], "k1")
        self.assertEqual(job["state"], "pending")
        self.assertEqual(run_next_approved(self.db), {"state": "idle"})

    def test_approved_runs_once(self):
        queued = queue_job(self.db, "count_records", ["A", "B"], "k2")
        decide_job(self.db, queued["id"], "approved")
        done = run_next_approved(self.db)
        self.assertEqual(done["result"], {"count": 2})
        self.assertEqual(done["state"], "completed")
        self.assertEqual(run_next_approved(self.db), {"state": "idle"})

    def test_retry_does_not_duplicate(self):
        first = queue_job(self.db, "count_records", [], "k3")
        second = queue_job(self.db, "count_records", [], "k3")
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(list_jobs(self.db)), 1)

    def test_conflicting_idempotency_rejected(self):
        queue_job(self.db, "count_records", ["A"], "k4")
        with self.assertRaises(GateError):
            queue_job(self.db, "count_records", ["B"], "k4")
        with self.assertRaises(GateError):
            queue_job(self.db, "find_duplicates", ["A"], "k4")

    def test_rejected_never_executes(self):
        queued = queue_job(self.db, "count_records", ["A"], "k5")
        decide_job(self.db, queued["id"], "rejected")
        self.assertEqual(run_next_approved(self.db), {"state": "idle"})
        with self.assertRaises(GateError):
            decide_job(self.db, queued["id"], "approved")

    def test_duplicate_analysis_is_read_only(self):
        queued = queue_job(self.db, "find_duplicates", [" Alpha ", "alpha", "BETA", "Beta", "Gamma"], "k6")
        decide_job(self.db, queued["id"], "approved")
        result = run_next_approved(self.db)["result"]
        self.assertEqual(result["duplicate_groups"], {"alpha": 2, "beta": 2})
        self.assertEqual(result["duplicate_extra_records"], 2)
        self.assertEqual(len(list_jobs(self.db)), 1)

    def test_unapproved_types_and_oversize_rejected(self):
        with self.assertRaises(GateError):
            queue_job(self.db, "send_email", ["A"], "k7")
        with self.assertRaises(GateError):
            queue_job(self.db, "count_records", ["x" * 101], "k8")
        with self.assertRaises(GateError):
            queue_job(self.db, "count_records", [1], "k9")
        with self.assertRaises(GateError):
            queue_job(self.db, "count_records", ["A"] * 1001, "k10")

    def test_audit_lifecycle(self):
        queued = queue_job(self.db, "count_records", ["A"], "k11")
        decide_job(self.db, queued["id"], "approved")
        run_next_approved(self.db)
        self.assertEqual([e["event"] for e in list_audit(self.db)], [
            "queued; requires explicit approval", "approved", "completed read-only operation"
        ])

    def test_persists_between_connections(self):
        path = os.path.join(self.tmp.name, "persist.db")
        first = connect(path)
        queued = queue_job(first, "count_records", ["A"], "persist")
        first.close()
        second = connect(path)
        self.assertEqual(list_jobs(second)[0]["id"], queued["id"])
        self.assertEqual(run_next_approved(second), {"state": "idle"})
        second.close()


if __name__ == "__main__":
    unittest.main()
