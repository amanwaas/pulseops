import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
import httpx

from app.core.config import settings

logger = logging.getLogger("pulseops.alerts")


class AlertDispatcher:
    """
    Production-grade Alert Dispatcher with exponential backoff retries.
    Supports Slack, Microsoft Teams, Generic Webhooks, and Email.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        await self.client.aclose()

    async def dispatch_alert(
        self,
        channel_type: str,
        destination_url_or_email: str,
        title: str,
        message: str,
        severity: str,  # 'CRITICAL', 'WARNING', 'RESOLVED', 'INFO'
        metadata: Dict[str, Any] = None,
    ):
        """Dispatches an alert with exponential backoff."""
        metadata = metadata or {}
        max_retries = 3
        backoff = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                if channel_type == "slack":
                    await self._send_slack(destination_url_or_email, title, message, severity, metadata)
                elif channel_type == "teams":
                    await self._send_teams(destination_url_or_email, title, message, severity, metadata)
                elif channel_type == "webhook":
                    await self._send_generic_webhook(destination_url_or_email, title, message, severity, metadata)
                elif channel_type == "email":
                    await self._send_email(destination_url_or_email, title, message, severity, metadata)
                else:
                    logger.warning(f"Unknown alert channel type: {channel_type}")
                    return

                logger.info(f"Successfully dispatched {severity} alert to {channel_type}")
                return
            except Exception as e:
                logger.warning(f"Alert dispatch attempt {attempt}/{max_retries} failed for {channel_type}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(f"Failed to dispatch alert to {channel_type} after {max_retries} attempts.")

    async def _send_slack(
        self,
        webhook_url: str,
        title: str,
        message: str,
        severity: str,
        metadata: Dict[str, Any],
    ):
        color_map = {
            "CRITICAL": "#E01E5A",  # Red
            "WARNING": "#ECB22E",   # Yellow
            "RESOLVED": "#2EB886",  # Green
            "INFO": "#2BAC76",
        }
        color = color_map.get(severity, "#4A154B")

        fields = []
        for k, v in metadata.items():
            fields.append({
                "title": k.replace("_", " ").title(),
                "value": str(v),
                "short": True,
            })

        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"[{severity}] {title}",
                    "text": message,
                    "fields": fields,
                    "footer": "PulseOps Monitoring Platform",
                    "ts": int(asyncio.get_event_loop().time()),
                }
            ]
        }
        resp = await self.client.post(webhook_url, json=payload)
        resp.raise_for_status()

    async def _send_teams(
        self,
        webhook_url: str,
        title: str,
        message: str,
        severity: str,
        metadata: Dict[str, Any],
    ):
        theme_color = "E01E5A" if severity == "CRITICAL" else ("2EB886" if severity == "RESOLVED" else "ECB22E")
        facts = [{"name": k.replace("_", " ").title(), "value": str(v)} for k, v in metadata.items()]

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": theme_color,
            "title": f"[{severity}] {title}",
            "sections": [
                {
                    "activityTitle": "PulseOps Monitoring Alert",
                    "text": message,
                    "facts": facts,
                }
            ],
        }
        resp = await self.client.post(webhook_url, json=payload)
        resp.raise_for_status()

    async def _send_generic_webhook(
        self,
        webhook_url: str,
        title: str,
        message: str,
        severity: str,
        metadata: Dict[str, Any],
    ):
        payload = {
            "event": "alert",
            "severity": severity,
            "title": title,
            "message": message,
            "metadata": metadata,
            "source": "PulseOps",
        }
        resp = await self.client.post(webhook_url, json=payload)
        resp.raise_for_status()

    async def _send_email(
        self,
        to_email: str,
        title: str,
        message: str,
        severity: str,
        metadata: Dict[str, Any],
    ):
        if not settings.SMTP_HOST:
            logger.info(f"Simulating email dispatch to {to_email}: [{severity}] {title}")
            return

        def _sync_smtp():
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{severity}] {title} - PulseOps"
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to_email

            body = f"{message}\n\nDetails:\n" + "\n".join(f"- {k}: {v}" for k, v in metadata.items())
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

        # Run blocking SMTP in thread pool to not stall async event loop
        await asyncio.to_thread(_sync_smtp)


alert_dispatcher = AlertDispatcher()
