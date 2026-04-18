# Email Drafter Agent

Auto-drafts Antora supply chain emails with Claude, pushes them to Gmail Drafts
and a Slack channel for approval, sends on approval, and learns from your edits.

## What it does

1. Trigger (Slack slash command, HTTP POST, or scheduled job) provides email
   type + minimal inputs.
2. Agent checks the priority allowlist. If the type is not in scope (see
   `src/priority.py`), it stops.
3. Agent drafts the email with Claude Opus 4.7 using the `email-drafter` skill
   (`.claude/skills/email-drafter/SKILL.md`) as the cached system prompt.
4. Agent writes the draft to Vincent's Gmail Drafts via the Gmail API.
5. Agent posts the draft to Slack channel `#agent-email-drafts` with
   **Approve / Edit / Reject** buttons.
6. On **Approve** → agent sends the Gmail draft (`gmail.send`).
7. On **Edit** → agent opens a Slack modal prefilled with the draft, captures
   the edited version, updates the Gmail draft, and re-posts for approval.
8. On **Reject** → agent deletes the Gmail draft and records the rejection.
9. Every `(original_draft, final_sent)` pair is persisted in Firestore. The
   learning module extracts edit patterns and injects the top-N recent diffs
   as few-shot examples in future drafting calls.

## Architecture

- **Hosting:** Google Cloud Run (scale-to-zero, ~$0/mo at low volume).
- **Storage:** Firestore (free tier).
- **Model:** `claude-opus-4-7` with adaptive thinking.
- **Framework:** FastAPI.
- **Auth:** Google OAuth 2.0 (reuses the same OAuth client as Daily SCM Agent).

## Scope (high-priority allowlist)

Only these email types run through the auto-pipeline. Expand by editing
`src/priority.py`.

- Supplier Expedite Request
- Delivery Delay Escalation
- Internal Risk Alert

All other 5 types stay manual — use the `email-drafter` skill directly in
Claude Code.

## Setup — step by step

### 1. Google Cloud project

Reuse the GCP project that already hosts Daily SCM Agent.

```bash
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable run.googleapis.com \
  gmail.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

### 2. Gmail OAuth scopes (Workspace admin step)

Gmail `compose` and `send` are restricted scopes. On the Antora Google
Workspace admin console, whitelist this OAuth client ID for:

- `https://www.googleapis.com/auth/gmail.compose`
- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/gmail.modify` (needed to delete drafts on reject)

**Admin console path:** Security → API controls → Manage Third-Party App
Access → Add app → OAuth App Name or Client ID → paste the OAuth client ID
from Daily SCM Agent → Trusted.

Without this, the agent cannot send mail from `vincent@antoraenergy.com`.

### 3. OAuth credentials

Copy the `client_secret.json` from Daily SCM Agent. Then run the one-time
consent flow locally:

```bash
cd agents/email_drafter_agent
python -m src.gmail_client authorize
```

This produces `token.json`. Upload it to Secret Manager:

```bash
gcloud secrets create email-drafter-gmail-token --data-file=token.json
```

### 4. Slack app

1. Create a Slack app at https://api.slack.com/apps → From scratch → name
   "Antora Email Drafter" → Antora workspace.
2. **OAuth & Permissions** → Bot Token Scopes:
   - `chat:write`
   - `channels:manage` (to create `#agent-email-drafts`)
   - `commands`
   - `users:read` (to map Slack user → Vincent)
3. Install to workspace. Copy the **Bot User OAuth Token** (`xoxb-...`) and
   **Signing Secret**.
4. **Slash Commands** → Create `/draft-email` → Request URL
   `https://<cloud-run-url>/slack/command`.
5. **Interactivity & Shortcuts** → enable → Request URL
   `https://<cloud-run-url>/slack/interact`.
6. Run the one-time setup to create the channel and invite Vincent:
   ```bash
   python -m src.slack_client setup
   ```

### 5. Firestore

```bash
gcloud firestore databases create --location=us-west1
```

No schema — collections (`drafts`, `edits`, `sent`) are created on first write.

### 6. Secrets

```bash
echo -n "<ANTHROPIC_KEY>"     | gcloud secrets create email-drafter-anthropic-key     --data-file=-
echo -n "<SLACK_BOT_TOKEN>"   | gcloud secrets create email-drafter-slack-bot-token   --data-file=-
echo -n "<SLACK_SIGNING>"     | gcloud secrets create email-drafter-slack-signing     --data-file=-
```

### 7. Deploy

```bash
./deploy.sh
```

This builds the container, pushes to Artifact Registry, and deploys to Cloud
Run with all secrets wired in.

### 8. Smoke test

```bash
curl -X POST https://<cloud-run-url>/draft \
  -H "Content-Type: application/json" \
  -d '{
    "email_type": "Supplier Expedite Request",
    "recipient_name": "Scott Van Pelt",
    "recipient_email": "scott@elitemetaldirect.com",
    "supplier": "Elite Metal Direct",
    "details": "PO #4521, busbars A1017095, scheduled May 15, need May 1, Gen1v5 line-down risk"
  }'
```

Expected: Gmail draft created, Slack message posted to `#agent-email-drafts`.

## Triggering from other agents

The `POST /draft` endpoint accepts the same JSON shape the `email-drafter`
skill expects. Daily SCM Agent can call it directly when it detects a
shortage, schedule slip, or expedite condition.

## Learning loop

On every approved-with-edits send, the agent stores:

- `original_draft` — what Claude generated
- `final_sent` — what was actually sent
- `email_type`, `supplier`, `timestamp`

`src/learning.py` pulls the most recent 10 edits for the same `email_type`
and appends them as a few-shot block to the system prompt on subsequent
drafts. Over time, tone/phrasing drift toward Vincent's real voice.

To inspect what Claude currently "knows":

```bash
curl https://<cloud-run-url>/learning/preview?email_type=Supplier+Expedite+Request
```

## Updating scope

Add a new email type to auto-pipeline:

```python
# src/priority.py
HIGH_PRIORITY = {
    "Supplier Expedite Request",
    "Delivery Delay Escalation",
    "Internal Risk Alert",
    "PO Status Follow-Up",  # <-- add here
}
```

Commit + redeploy.
