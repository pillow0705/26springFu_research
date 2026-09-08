# Academic Center Group Meeting Protocol

## Purpose

The Academic Center Committee organizes durable group meetings. A meeting collects each participant's statement, routes statements to peer participants for discussion, returns the complete discussion packet, and requires every participant to internalize it in a personal synthesis.

## Workflow

1. Read the meeting brief at `workspace/group_meeting/<meeting_id>/brief.md` and read any committee message.
2. Submit one clear statement with `committee_submit_meeting_statement`. Use `content` for text or `relative_path` for a UTF-8 file relative to `03/`.
3. Read other statements with `committee_get_meeting_discussion` and comment on another participant's statement with `committee_submit_meeting_comment`.
4. Wait for the committee to return the meeting. Read `workspace/group_meeting/<meeting_id>/committee-feedback.md` in full.
5. Compress, reconcile, and internalize the discussion in your own words. Submit that synthesis with `committee_submit_meeting_synthesis`.

## Rules

- Use only the Academic Center Committee MCP interfaces for meeting communication.
- Keep claims precise and identify assumptions, disagreements, and unresolved points.
- Comments must address another participant's statement; do not use the meeting to submit review decisions.
- The meeting is complete for you only after your internalized synthesis is written and submitted.

