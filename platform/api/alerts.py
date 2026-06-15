"""
Alert delivery — Slack webhook + email.
Called by the nightly orchestrator after anomaly detection.

Config (in .env):
    SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
    ALERT_EMAIL_TO=team@lofi.nl
    ALERT_EMAIL_FROM=intelligence@lofi.nl
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=
    SMTP_PASSWORD=
"""

import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional

import httpx

SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
ALERT_EMAIL_TO:    Optional[str] = os.getenv("ALERT_EMAIL_TO")
ALERT_EMAIL_FROM:  Optional[str] = os.getenv("ALERT_EMAIL_FROM")
SMTP_HOST:  str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT:  int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER:  Optional[str] = os.getenv("SMTP_USER")
SMTP_PASS:  Optional[str] = os.getenv("SMTP_PASSWORD")


# Route-map alert language mapped from internal direction codes
_LABELS = {
    ("artist_anomaly", "spike"): "Pay attention to this artist now",
    ("artist_anomaly", "drop"):  "Momentum alert — check this artist",
    ("market_trend",   "emerging"):  "Genre trend emerging",
    ("market_trend",   "declining"): "Genre trend declining",
}


def _format_slack_blocks(alerts: list[dict]) -> list[dict]:
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": "LOFI Artist Intelligence — Alerts"}}]
    for a in alerts[:20]:
        label = _LABELS.get((a["type"], a.get("direction", "")), "Alert")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{label}*\n{a['message']}"},
        })
    if len(alerts) > 20:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"_+{len(alerts) - 20} more alerts — check the dashboard_"}],
        })
    return blocks


def send_slack(alerts: list[dict]) -> bool:
    if not SLACK_WEBHOOK_URL or not alerts:
        return False
    try:
        resp = httpx.post(
            SLACK_WEBHOOK_URL,
            json={"blocks": _format_slack_blocks(alerts)},
            timeout=10,
        )
        resp.raise_for_status()
        print(f"Slack: sent {len(alerts)} alerts")
        return True
    except Exception as e:
        print(f"Slack delivery failed: {e}")
        return False


def send_email(alerts: list[dict], subject: str = "LOFI Artist Intelligence — Daily Alerts") -> bool:
    if not all([ALERT_EMAIL_TO, ALERT_EMAIL_FROM, SMTP_USER, SMTP_PASS]) or not alerts:
        return False
    try:
        lines = [f"LOFI Artist Intelligence — {len(alerts)} alerts\n"]
        for a in alerts:
            label = _LABELS.get((a["type"], a.get("direction", "")), "Alert")
            lines.append(f"[{label}]\n{a['message']}\n")

        msg = MIMEText("\n".join(lines))
        msg["Subject"] = subject
        msg["From"]    = ALERT_EMAIL_FROM
        msg["To"]      = ALERT_EMAIL_TO

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)

        print(f"Email: sent {len(alerts)} alerts to {ALERT_EMAIL_TO}")
        return True
    except Exception as e:
        print(f"Email delivery failed: {e}")
        return False


def dispatch(alerts: list[dict]):
    """Send all alerts via every configured channel."""
    if not alerts:
        print("No alerts to dispatch.")
        return
    send_slack(alerts)
    send_email(alerts)
