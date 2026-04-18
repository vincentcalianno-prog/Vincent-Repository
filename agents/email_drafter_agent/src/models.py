from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class DraftRequest:
    email_type: str
    recipient_name: str
    recipient_email: str
    supplier: str | None = None
    details: str = ""
    deadline: str | None = None
    cc: list[str] = field(default_factory=list)


@dataclass
class EmailDraft:
    email_type: str
    recipient_name: str
    recipient_email: str
    supplier: str | None
    subject: str
    body: str
    goal: str
    follow_up: str
    raw_model_output: str
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now)
    gmail_draft_id: str | None = None
    slack_channel: str | None = None
    slack_ts: str | None = None
    status: str = "drafted"  # drafted | edited | approved | sent | rejected

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Edit:
    draft_id: str
    edited_subject: str
    edited_body: str
    editor_slack_user: str
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SentEmail:
    draft_id: str
    email_type: str
    subject: str
    body: str
    gmail_message_id: str
    original_subject: str
    original_body: str
    id: str = field(default_factory=_new_id)
    sent_at: str = field(default_factory=_now)

    @property
    def was_edited(self) -> bool:
        return (self.subject, self.body) != (self.original_subject, self.original_body)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["was_edited"] = self.was_edited
        return d
