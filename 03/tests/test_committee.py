import json
import tempfile
import unittest
from pathlib import Path

from committee.service import CommitteeService


class CommitteeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "03"
        for idx in (5, 6):
            (self.root / "agent" / f"math{idx}" / "results").mkdir(parents=True)
        (self.root / "agent" / "math5" / "results" / "proof.md").write_text(
            "# Type II(1) proof\n", encoding="utf-8"
        )
        (self.root / "agent" / "math6" / "results" / "proof.md").write_text(
            "# Type II(3) proof\n", encoding="utf-8"
        )
        self.service = CommitteeService(
            self.root,
            db_path=self.root / "runtime" / "committee.sqlite",
            enable_sdk=False,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_manuscript_is_copied_to_matching_reviewer(self) -> None:
        record = self.service.submit_manuscript(
            "math5", "v1", "agent/math5/results/proof.md", "Initial proof", task_id="S5"
        )
        self.assertEqual(record["reviewer_id"], "review5")
        self.assertEqual(record["status"], "SENT_TO_REVIEWER")
        self.assertTrue((self.root / record["review_path"]).exists())

    def test_relative_path_cannot_escape_root(self) -> None:
        with self.assertRaises(ValueError):
            self.service.submit_manuscript(
                "math5", "v1", "../../outside.md", "Invalid", task_id="S5"
            )

    def test_reviewer_decision_is_stored_and_delivered_as_message(self) -> None:
        record = self.service.submit_manuscript(
            "math5", "v1", "agent/math5/results/proof.md", "Initial proof", task_id="S5"
        )
        reviewed = self.service.submit_review(
            "review5", record["submission_id"], "APPROVE", "The core argument is sound."
        )
        self.assertEqual(reviewed["status"], "APPROVED")
        self.assertEqual(self.service.get_review_result("math5")[0]["decision"], "APPROVE")
        messages = self.service.get_messages("math5")
        self.assertEqual(messages[0]["from_agent"], "review5")

    def test_launch_manifest_is_read_without_writing_to_it(self) -> None:
        launch = self.root / "runtime" / "launch.json"
        launch.parent.mkdir(parents=True, exist_ok=True)
        launch.write_text(json.dumps({"agents": {"review5": {"thread_id": "t5"}}}), encoding="utf-8")
        before = launch.read_text(encoding="utf-8")
        self.assertEqual(self.service.health()["launch_loaded"], True)
        self.assertEqual(launch.read_text(encoding="utf-8"), before)

    def test_group_meeting_roundtrip(self) -> None:
        meeting = self.service.create_meeting(
            "S5 checkpoint", "Collect and compare statement arguments", participants=["math5", "math6"], created_by="Writer"
        )
        sid5 = self.service.submit_meeting_statement(
            "math5", meeting["meeting_id"], content="math5 idea"
        )["statement_id"]
        self.service.submit_meeting_statement("math6", meeting["meeting_id"], content="math6 idea")
        comment = self.service.submit_meeting_comment(
            "math6", meeting["meeting_id"], sid5, "Potential missing lemma step"
        )

        discussion = self.service.get_meeting_discussion(meeting["meeting_id"], requester="math5")
        self.assertEqual(discussion["meeting"]["status"], "OPEN")
        self.assertEqual(len(discussion["statements"]), 2)
        self.assertEqual(len(discussion["comments"]), 1)
        self.assertEqual(comment["statement_id"], sid5)

        returned = self.service.finalize_meeting(meeting["meeting_id"], finalized_by="Writer")
        self.assertEqual(returned["status"], "RETURNED")
        for agent_id in ("math5", "math6"):
            path = self.root / f"agent/{agent_id}/workspace/group_meeting/{meeting['meeting_id']}/committee-feedback.md"
            self.assertTrue(path.exists())

        self.service.submit_meeting_synthesis("math5", meeting["meeting_id"], "math5 synthesis")
        self.service.submit_meeting_synthesis("math6", meeting["meeting_id"], "math6 synthesis")
        syntheses = self.service.get_meeting_syntheses(meeting["meeting_id"], requester="Writer")
        self.assertEqual(len(syntheses), 2)

    def test_group_meeting_forbids_self_comment_and_late_synthesis(self) -> None:
        meeting = self.service.create_meeting(
            "S5 checkpoint", "Self-comment guard", participants=["math5", "math6"]
        )
        sid = self.service.submit_meeting_statement(
            "math5", meeting["meeting_id"], content="math5 idea"
        )["statement_id"]
        with self.assertRaises(ValueError):
            self.service.submit_meeting_comment(
                "math5", meeting["meeting_id"], sid, "self comment"
            )
        self.service.finalize_meeting(meeting["meeting_id"])
        with self.assertRaises(ValueError):
            self.service.submit_meeting_statement("math5", meeting["meeting_id"], content="too late")


if __name__ == "__main__":
    unittest.main()
