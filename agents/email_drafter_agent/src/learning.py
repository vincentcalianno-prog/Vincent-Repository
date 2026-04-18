"""Build a few-shot examples block from recent (original → final) edit pairs.

Only edited-and-sent emails contribute — if Vincent sent without changes, the
original draft was already correct and adds no signal.
"""
from __future__ import annotations

from . import config, store


def recent_examples_block(email_type: str) -> str:
    examples = store.recent_sent_for_type(email_type, config.LEARNING_EXAMPLES_PER_TYPE)
    if not examples:
        return ""

    sections: list[str] = [
        "## Recent edits for this email type (learn from these revisions)",
        "",
        "Below are recent drafts the model generated alongside the final version "
        "Vincent actually sent. Pattern-match on tone, phrasing, brevity, and "
        "structural choices. Emulate the FINAL version style on the next draft.",
        "",
    ]
    for i, row in enumerate(examples, 1):
        sections.extend([
            f"### Example {i}",
            "**Original draft:**",
            f"Subject: {row.get('original_subject', '')}",
            "",
            str(row.get("original_body", "")),
            "",
            "**Final sent:**",
            f"Subject: {row.get('subject', '')}",
            "",
            str(row.get("body", "")),
            "",
            "---",
            "",
        ])
    return "\n".join(sections)
