import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from lab import ResearchLab


class ResearchLabTests(unittest.TestCase):
    @contextmanager
    def make_lab(self):
        source = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "lab"
            root.mkdir()
            (root / "config").mkdir()
            (root / "prompts").mkdir()
            config = json.loads((source / "config" / "team.json").read_text())
            for role, data in config["roles"].items():
                target = root / data["prompt"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"Role {role}")
            (root / "config" / "team.json").write_text(json.dumps(config))
            yield ResearchLab(root)

    def test_dry_run_records_bounded_turns(self):
        with self.make_lab() as lab:
            results = lab.run("Test task", max_turns=3, dry_run=True)
            self.assertEqual(len(results), 3)
            self.assertEqual(lab.turns, 3)
            self.assertTrue(all(result.artifact.exists() for result in results))

    def test_stop_file_is_honored(self):
        with self.make_lab() as lab:
            lab.request_stop()
            self.assertEqual(lab.run("Test task", max_turns=2, dry_run=True), [])

    def test_action_protocol_is_generic(self):
        with self.make_lab() as lab:
            actions = lab._parse_actions(
                "ACTION: MESSAGE voisin | Compare this case.\n"
                "ACTION: MEETING markman,lie_fu | Debate the obstruction.\n"
                "ACTION: WAIT | No new work."
            )
            self.assertEqual([action["kind"] for action in actions], ["MESSAGE", "MEETING", "WAIT"])


if __name__ == "__main__":
    unittest.main()
