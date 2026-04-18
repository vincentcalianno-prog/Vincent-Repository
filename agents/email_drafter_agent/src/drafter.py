"""Claude Opus 4.7 drafting client.

Loads the `email-drafter` skill as a cached system prompt. Appends recent
edits as few-shot examples so the model learns Vincent's voice over time.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from anthropic import Anthropic

from . import config
from .learning import recent_examples_block
from .models import DraftRequest, EmailDraft

_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)


@lru_cache(maxsize=1)
def _skill_text() -> str:
    return config.SKILL_PATH.read_text()


def _system_blocks(email_type: str) -> list[dict[str, Any]]:
    skill = _skill_text()
    examples = recent_examples_block(email_type)
    blocks: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": skill,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if examples:
        blocks.append({"type": "text", "text": examples})
    return blocks


def _user_prompt(req: DraftRequest) -> str:
    payload = {
        "email_type": req.email_type,
        "recipient_name": req.recipient_name,
        "recipient_email": req.recipient_email,
        "supplier": req.supplier,
        "details": req.details,
        "deadline": req.deadline,
        "cc": req.cc,
    }
    return (
        "Draft this email. Follow the skill's output format exactly — "
        "Subject, Body, Goal, Follow-up.\n\n"
        f"Inputs:\n{json.dumps(payload, indent=2)}"
    )


def _parse_output(text: str) -> tuple[str, str, str, str]:
    def section(label: str) -> str:
        needle = f"**{label}:**"
        idx = text.find(needle)
        if idx == -1:
            return ""
        start = idx + len(needle)
        rest = text[start:]
        next_header = len(rest)
        for other in ("**Subject:**", "**Body:**", "**Goal:**", "**Follow-up"):
            if other == needle:
                continue
            pos = rest.find(other)
            if pos != -1 and pos < next_header:
                next_header = pos
        return rest[:next_header].strip()

    return (
        section("Subject"),
        section("Body"),
        section("Goal"),
        section("Follow-up (if no response in 48 hrs)") or section("Follow-up"),
    )


def draft(req: DraftRequest) -> EmailDraft:
    response = _client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=_system_blocks(req.email_type),
        messages=[{"role": "user", "content": _user_prompt(req)}],
    )
    text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    subject, body, goal, follow_up = _parse_output(text)
    return EmailDraft(
        email_type=req.email_type,
        recipient_name=req.recipient_name,
        recipient_email=req.recipient_email,
        supplier=req.supplier,
        subject=subject,
        body=body,
        goal=goal,
        follow_up=follow_up,
        raw_model_output=text,
    )
