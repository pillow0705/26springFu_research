#!/usr/bin/env python3
"""Run the simulated algebra research laboratory."""

from __future__ import annotations

import argparse
from pathlib import Path

from lab import ResearchLab


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="Develop a rigorous research plan for the 6-dimensional Hodge-class problem.")
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--meeting", action="store_true", help="Seed one externally requested meeting after the event queue.")
    args = parser.parse_args()

    lab = ResearchLab(Path(__file__).resolve().parent)
    results = lab.run(args.task, max_turns=args.max_turns, dry_run=args.dry_run)
    if args.meeting and not lab.should_stop():
        results.extend(lab.group_meeting(dry_run=args.dry_run))
    for result in results:
        print(f"{result.role}: {result.artifact} ({result.elapsed_seconds:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
