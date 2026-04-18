import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "email-drafter" / "SKILL.md"

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "agent-email-drafts")

GMAIL_TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", "/secrets/gmail_token.json")
GMAIL_CLIENT_SECRET_PATH = os.environ.get(
    "GMAIL_CLIENT_SECRET_PATH", "/secrets/gmail_client_secret.json"
)
VINCENT_EMAIL = os.environ.get("VINCENT_EMAIL", "vincent@antoraenergy.com")

GCP_PROJECT = os.environ["GCP_PROJECT"]
FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "(default)")

LEARNING_EXAMPLES_PER_TYPE = int(os.environ.get("LEARNING_EXAMPLES_PER_TYPE", "10"))
