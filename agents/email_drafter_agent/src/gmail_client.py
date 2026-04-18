"""Gmail API client — create, update, send, delete drafts.

Runs on Vincent's Antora Google Workspace account. Requires admin-whitelisted
OAuth client (see README step 2). Reuses credentials from Daily SCM Agent.

CLI:
    python -m src.gmail_client authorize   # one-time local consent flow
"""
from __future__ import annotations

import base64
import json
import sys
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _load_credentials() -> Credentials:
    token_path = Path(config.GMAIL_TOKEN_PATH)
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    return creds


@lru_cache(maxsize=1)
def _service():
    return build("gmail", "v1", credentials=_load_credentials(), cache_discovery=False)


def _encode(msg: EmailMessage) -> str:
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def _build_message(to: str, subject: str, body: str, cc: list[str] | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = config.VINCENT_EMAIL
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(body)
    return msg


def create_draft(to: str, subject: str, body: str, cc: list[str] | None = None) -> str:
    msg = _build_message(to, subject, body, cc)
    resp = (
        _service()
        .users()
        .drafts()
        .create(userId="me", body={"message": {"raw": _encode(msg)}})
        .execute()
    )
    return resp["id"]


def update_draft(draft_id: str, to: str, subject: str, body: str, cc: list[str] | None = None) -> None:
    msg = _build_message(to, subject, body, cc)
    _service().users().drafts().update(
        userId="me",
        id=draft_id,
        body={"message": {"raw": _encode(msg)}},
    ).execute()


def send_draft(draft_id: str) -> str:
    resp = _service().users().drafts().send(userId="me", body={"id": draft_id}).execute()
    return resp["id"]


def delete_draft(draft_id: str) -> None:
    _service().users().drafts().delete(userId="me", id=draft_id).execute()


def _authorize_cli() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(config.GMAIL_CLIENT_SECRET_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    Path(config.GMAIL_TOKEN_PATH).write_text(creds.to_json())
    print(f"Wrote {config.GMAIL_TOKEN_PATH}")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "authorize":
        _authorize_cli()
    else:
        print("usage: python -m src.gmail_client authorize", file=sys.stderr)
        sys.exit(1)
