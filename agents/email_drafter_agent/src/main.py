"""FastAPI app — HTTP trigger, Slack slash command, Slack interactivity."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from . import config, drafter, gmail_client, slack_client, store
from .models import DraftRequest, Edit, EmailDraft, SentEmail
from .priority import is_high_priority

app = FastAPI(title="Antora Email Drafter Agent")


class DraftIn(BaseModel):
    email_type: str
    recipient_name: str
    recipient_email: str
    supplier: str | None = None
    details: str = ""
    deadline: str | None = None
    cc: list[str] = Field(default_factory=list)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/draft")
def draft_endpoint(payload: DraftIn) -> dict[str, Any]:
    if not is_high_priority(payload.email_type):
        raise HTTPException(
            status_code=400,
            detail=f"{payload.email_type} is not in the high-priority allowlist. "
                   "Use the email-drafter skill manually or expand src/priority.py.",
        )
    return _draft_and_post(DraftRequest(**payload.model_dump()))


def _draft_and_post(req: DraftRequest) -> dict[str, Any]:
    draft = drafter.draft(req)
    cc = req.cc or None
    draft.gmail_draft_id = gmail_client.create_draft(
        to=req.recipient_email, subject=draft.subject, body=draft.body, cc=cc
    )
    channel, ts = slack_client.post_draft_for_approval(draft)
    draft.slack_channel = channel
    draft.slack_ts = ts
    store.save_draft(draft)
    return {"draft_id": draft.id, "gmail_draft_id": draft.gmail_draft_id, "slack_ts": ts}


# ---- Slack ----

def _verify_slack(request: Request, body: bytes) -> None:
    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")
    if not ts or not sig:
        raise HTTPException(status_code=401, detail="missing slack signature")
    if abs(time.time() - int(ts)) > 60 * 5:
        raise HTTPException(status_code=401, detail="stale slack timestamp")
    basestring = b"v0:" + ts.encode() + b":" + body
    expected = "v0=" + hmac.new(
        config.SLACK_SIGNING_SECRET.encode(), basestring, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="bad slack signature")


@app.post("/slack/command")
async def slack_command(request: Request) -> dict[str, Any]:
    body = await request.body()
    _verify_slack(request, body)
    form = {k: v[0] for k, v in parse_qs(body.decode()).items()}
    text = form.get("text", "").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {
            "response_type": "ephemeral",
            "text": "Send a JSON body, e.g. `/draft-email {\"email_type\":\"Supplier Expedite Request\",\"recipient_name\":\"Scott\",\"recipient_email\":\"scott@x.com\",\"details\":\"...\"}`",
        }
    if not is_high_priority(payload.get("email_type", "")):
        return {"response_type": "ephemeral", "text": "Not in high-priority allowlist."}
    result = _draft_and_post(DraftRequest(**payload))
    return {"response_type": "ephemeral", "text": f"Draft posted: {result['draft_id']}"}


@app.post("/slack/interact")
async def slack_interact(request: Request) -> dict[str, Any]:
    body = await request.body()
    _verify_slack(request, body)
    form = {k: v[0] for k, v in parse_qs(body.decode()).items()}
    payload = json.loads(form["payload"])
    kind = payload.get("type")
    if kind == "block_actions":
        return _handle_block_action(payload)
    if kind == "view_submission":
        return _handle_view_submission(payload)
    return {}


def _handle_block_action(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload["actions"][0]
    action_id = action["action_id"]
    draft_id = action["value"]
    user = payload["user"]["id"]
    draft = store.get_draft(draft_id)
    if not draft:
        return {}

    if action_id == "approve":
        gmail_msg_id = gmail_client.send_draft(draft.gmail_draft_id)
        sent = SentEmail(
            draft_id=draft.id,
            email_type=draft.email_type,
            subject=draft.subject,
            body=draft.body,
            gmail_message_id=gmail_msg_id,
            original_subject=draft.subject,
            original_body=draft.body,
        )
        # was_edited only true if status was "edited"
        if draft.status == "edited":
            sent.original_subject = _original_subject(draft) or draft.subject
            sent.original_body = _original_body(draft) or draft.body
        store.save_sent(sent)
        store.update_draft(draft.id, {"status": "sent"})
        slack_client.update_draft_message(
            draft.slack_channel, draft.slack_ts, draft, status_note="SENT"
        )
        return {}

    if action_id == "reject":
        gmail_client.delete_draft(draft.gmail_draft_id)
        store.update_draft(draft.id, {"status": "rejected"})
        slack_client.update_draft_message(
            draft.slack_channel, draft.slack_ts, draft, status_note="REJECTED"
        )
        return {}

    if action_id == "edit":
        slack_client.open_edit_modal(payload["trigger_id"], draft)
        return {}

    return {}


def _handle_view_submission(payload: dict[str, Any]) -> dict[str, Any]:
    view = payload["view"]
    if view.get("callback_id") != "edit_submit":
        return {}
    draft_id = view["private_metadata"]
    values = view["state"]["values"]
    new_subject = values["subject_block"]["subject"]["value"]
    new_body = values["body_block"]["body"]["value"]
    user = payload["user"]["id"]

    draft = store.get_draft(draft_id)
    if not draft:
        return {}

    store.save_edit(Edit(
        draft_id=draft.id,
        edited_subject=new_subject,
        edited_body=new_body,
        editor_slack_user=user,
    ))
    # preserve original for learning signal
    orig_subject = _original_subject(draft) or draft.subject
    orig_body = _original_body(draft) or draft.body
    store.update_draft(draft.id, {
        "status": "edited",
        "subject": new_subject,
        "body": new_body,
        "original_subject_for_learning": orig_subject,
        "original_body_for_learning": orig_body,
    })
    gmail_client.update_draft(
        draft.gmail_draft_id,
        to=draft.recipient_email,
        subject=new_subject,
        body=new_body,
    )
    draft.subject = new_subject
    draft.body = new_body
    draft.status = "edited"
    slack_client.update_draft_message(
        draft.slack_channel, draft.slack_ts, draft, status_note="EDITED — re-approve to send"
    )
    return {"response_action": "clear"}


def _original_subject(draft: EmailDraft) -> str | None:
    return getattr(draft, "original_subject_for_learning", None)


def _original_body(draft: EmailDraft) -> str | None:
    return getattr(draft, "original_body_for_learning", None)


@app.get("/learning/preview")
def learning_preview(email_type: str) -> dict[str, Any]:
    from .learning import recent_examples_block
    return {"email_type": email_type, "examples": recent_examples_block(email_type)}
