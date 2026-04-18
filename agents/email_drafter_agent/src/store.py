"""Firestore persistence for drafts, edits, and sent emails."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from google.cloud import firestore

from . import config
from .models import EmailDraft, Edit, SentEmail


@lru_cache(maxsize=1)
def _db() -> firestore.Client:
    return firestore.Client(project=config.GCP_PROJECT, database=config.FIRESTORE_DATABASE)


# ---- drafts ----

def save_draft(draft: EmailDraft) -> None:
    _db().collection("drafts").document(draft.id).set(draft.to_dict())


def get_draft(draft_id: str) -> EmailDraft | None:
    snap = _db().collection("drafts").document(draft_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data.pop("id", None)
    return EmailDraft(id=draft_id, **data)


def update_draft(draft_id: str, fields: dict[str, Any]) -> None:
    _db().collection("drafts").document(draft_id).update(fields)


# ---- edits ----

def save_edit(edit: Edit) -> None:
    _db().collection("edits").document(edit.id).set(edit.to_dict())


# ---- sent ----

def save_sent(sent: SentEmail) -> None:
    _db().collection("sent").document(sent.id).set(sent.to_dict())


def recent_sent_for_type(email_type: str, limit: int) -> list[dict[str, Any]]:
    q = (
        _db()
        .collection("sent")
        .where("email_type", "==", email_type)
        .where("was_edited", "==", True)
        .order_by("sent_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    return [doc.to_dict() for doc in q.stream()]
