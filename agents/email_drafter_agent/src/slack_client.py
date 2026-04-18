"""Slack integration — channel setup, approval messages, edit modal.

CLI:
    python -m src.slack_client setup    # create #agent-email-drafts
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from typing import Any

from slack_sdk import WebClient

from . import config
from .models import EmailDraft


@lru_cache(maxsize=1)
def _client() -> WebClient:
    return WebClient(token=config.SLACK_BOT_TOKEN)


def _channel_id() -> str:
    cursor = None
    while True:
        resp = _client().conversations_list(
            exclude_archived=True, types="public_channel,private_channel", cursor=cursor
        )
        for ch in resp["channels"]:
            if ch["name"] == config.SLACK_CHANNEL:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    raise RuntimeError(f"Channel #{config.SLACK_CHANNEL} not found. Run setup.")


def post_draft_for_approval(draft: EmailDraft) -> tuple[str, str]:
    blocks = _draft_blocks(draft)
    resp = _client().chat_postMessage(
        channel=_channel_id(),
        text=f"Draft: {draft.subject}",
        blocks=blocks,
    )
    return resp["channel"], resp["ts"]


def update_draft_message(channel: str, ts: str, draft: EmailDraft, status_note: str = "") -> None:
    blocks = _draft_blocks(draft, status_note=status_note)
    _client().chat_update(channel=channel, ts=ts, text=f"Draft: {draft.subject}", blocks=blocks)


def _draft_blocks(draft: EmailDraft, status_note: str = "") -> list[dict[str, Any]]:
    header = f"*To:* {draft.recipient_name} <{draft.recipient_email}>  |  *Type:* {draft.email_type}"
    if draft.supplier:
        header += f"  |  *Supplier:* {draft.supplier}"
    if status_note:
        header = f":information_source: *{status_note}*\n" + header

    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Subject:* {draft.subject}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"```{draft.body}```"}},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"*Goal:* {draft.goal}"},
            {"type": "mrkdwn", "text": f"*Follow-up:* {draft.follow_up}"},
        ]},
    ]
    if draft.status in ("drafted", "edited"):
        blocks.append({
            "type": "actions",
            "block_id": "approval",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Approve & Send"},
                    "action_id": "approve",
                    "value": draft.id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Edit"},
                    "action_id": "edit",
                    "value": draft.id,
                },
                {
                    "type": "button",
                    "style": "danger",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "action_id": "reject",
                    "value": draft.id,
                },
            ],
        })
    return blocks


def open_edit_modal(trigger_id: str, draft: EmailDraft) -> None:
    view = {
        "type": "modal",
        "callback_id": "edit_submit",
        "private_metadata": draft.id,
        "title": {"type": "plain_text", "text": "Edit Draft"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "subject_block",
                "label": {"type": "plain_text", "text": "Subject"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "subject",
                    "initial_value": draft.subject,
                },
            },
            {
                "type": "input",
                "block_id": "body_block",
                "label": {"type": "plain_text", "text": "Body"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "body",
                    "multiline": True,
                    "initial_value": draft.body,
                },
            },
        ],
    }
    _client().views_open(trigger_id=trigger_id, view=view)


def _setup_cli() -> None:
    c = _client()
    try:
        resp = c.conversations_create(name=config.SLACK_CHANNEL, is_private=False)
        channel_id = resp["channel"]["id"]
        print(f"Created #{config.SLACK_CHANNEL} -> {channel_id}")
    except Exception as exc:
        print(f"Channel may already exist: {exc}")
        channel_id = _channel_id()
        print(f"Using existing channel {channel_id}")

    me = c.auth_test()
    print(json.dumps({"bot_user_id": me["user_id"], "channel_id": channel_id}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "setup":
        _setup_cli()
    else:
        print("usage: python -m src.slack_client setup", file=sys.stderr)
        sys.exit(1)
