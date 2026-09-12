---
name: memory
description: "Use when: creating or updating a simple project memory log, tracking session notes, capturing past conversations, or maintaining concise working history in a markdown file."
---

# Memory Log Skill

## Purpose

Maintain a lightweight markdown memory file that records what was discussed, decided, or completed in a project. This keeps later sessions grounded in prior work without creating a long-form document.

## Workflow

1. Decide the target file.
   - Prefer a root-level file such as `memory.md` for user-scoped notes.
   - If the project already has a memory log, update it instead of creating a duplicate.

2. Keep entries brief and dated.
   - Use a simple format like `- YYYY-MM-DD: summary of the work or decision.`
   - One entry per relevant action or conversation is enough.

3. Capture the essential facts.
   - What changed?
   - What was decided?
   - What should be revisited later?

4. Avoid noise.
   - Do not include long transcripts.
   - Do not record redundant details.
   - Focus on decisions, outcomes, and next steps.

5. Update incrementally.
   - Add only new information when the work continues.
   - Keep the log readable and easy to scan.

## Quality checks

- File exists and is easy to locate.
- Entries are dated and concise.
- Notes reflect real decisions or progress.
- No excessive duplication or long narrative.
- The log remains useful for future sessions.

## Example format

```md
# Memory

- 2026-09-12: Created a concise project memory log for session tracking.
- 2026-09-12: Confirmed the current task and saved the note in the workspace.
```

## When to use this skill

Use this when the user asks to:
- create a memory log
- save session history
- summarize recent work in a compact markdown file
- track decisions or follow-up notes for a project
