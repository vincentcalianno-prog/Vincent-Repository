"""High-priority email types that flow through the auto-pipeline.

Everything else falls back to manual use of the `email-drafter` skill.
Expand this set and redeploy to widen scope.
"""

HIGH_PRIORITY: set[str] = {
    "Supplier Expedite Request",
    "Delivery Delay Escalation",
    "Internal Risk Alert",
}


def is_high_priority(email_type: str) -> bool:
    return email_type in HIGH_PRIORITY
