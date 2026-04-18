#!/usr/bin/env bash
# Deploy the email-drafter agent to Cloud Run.
# Run from repo root: ./agents/email_drafter_agent/deploy.sh

set -euo pipefail

: "${GCP_PROJECT:?GCP_PROJECT must be set}"
REGION="${REGION:-us-west1}"
SERVICE="${SERVICE:-email-drafter-agent}"
VINCENT_EMAIL="${VINCENT_EMAIL:-vincent@antoraenergy.com}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "==> Deploying $SERVICE to $GCP_PROJECT / $REGION"

gcloud run deploy "$SERVICE" \
  --project "$GCP_PROJECT" \
  --region "$REGION" \
  --source . \
  --dockerfile agents/email_drafter_agent/Dockerfile \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --set-env-vars "GCP_PROJECT=$GCP_PROJECT,VINCENT_EMAIL=$VINCENT_EMAIL,SLACK_CHANNEL=agent-email-drafts,CLAUDE_MODEL=claude-opus-4-7,GMAIL_TOKEN_PATH=/secrets/gmail_token.json,GMAIL_CLIENT_SECRET_PATH=/secrets/gmail_client_secret.json" \
  --set-secrets "ANTHROPIC_API_KEY=email-drafter-anthropic-key:latest,SLACK_BOT_TOKEN=email-drafter-slack-bot-token:latest,SLACK_SIGNING_SECRET=email-drafter-slack-signing:latest,/secrets/gmail_token.json=email-drafter-gmail-token:latest,/secrets/gmail_client_secret.json=email-drafter-gmail-client-secret:latest"

URL=$(gcloud run services describe "$SERVICE" --project "$GCP_PROJECT" --region "$REGION" --format="value(status.url)")
echo ""
echo "Deployed: $URL"
echo "Update Slack app:"
echo "  - Slash command request URL: $URL/slack/command"
echo "  - Interactivity request URL:  $URL/slack/interact"
