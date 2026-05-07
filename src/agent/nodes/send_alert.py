import os
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode
from urllib.request import urlopen

from src.agent.state import AgentState
from src.config import load_env


load_env()


def send_alert(state: AgentState) -> AgentState:
    risk = state.get("risk", {})
    llm_analysis = state.get("llm_analysis", {})
    severity = risk.get("severity", "low")
    report_text = state.get("report_text", "")
    pdf_path = state.get("pdf_path")

    if severity == "high":
        telegram = _send_telegram_alert(report_text, pdf_path)
        return {
            **state,
            "alert_status": {
                "sent": telegram["sent"],
                "channel": "telegram",
                "detail": telegram["detail"],
            },
        }

    if severity == "medium" or llm_analysis.get("send_engineer_alert"):
        telegram = _send_telegram_alert(_summary(report_text), None)
        email = _send_email_alert(_summary(report_text))
        return {
            **state,
            "alert_status": {
                "sent": telegram["sent"] or email["sent"],
                "channel": "telegram/email",
                "detail": f"telegram={telegram['detail']}; email={email['detail']}",
            },
        }

    return {
        **state,
        "alert_status": {
            "sent": False,
            "channel": "report_only",
            "detail": "low severity, report saved only",
        },
    }


def _send_telegram_alert(message: str, pdf_path: str | None) -> dict[str, object]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"sent": False, "detail": "telegram env vars not configured"}

    try:
        query = urlencode({"chat_id": chat_id, "text": message[:3500]})
        with urlopen(f"https://api.telegram.org/bot{token}/sendMessage?{query}", timeout=5) as response:
            response.read()
        if pdf_path:
            return {"sent": True, "detail": f"telegram summary sent; pdf saved at {pdf_path}"}
        return {"sent": True, "detail": "telegram summary sent"}
    except Exception as exc:
        return {"sent": False, "detail": str(exc)}


def _send_email_alert(message: str) -> dict[str, object]:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    smtp_to = os.getenv("ALERT_EMAIL_TO")
    smtp_from = os.getenv("ALERT_EMAIL_FROM", smtp_username or smtp_to or "")
    if not smtp_host or not smtp_to:
        return {"sent": False, "detail": "email env vars not configured"}

    try:
        email = EmailMessage()
        email["From"] = smtp_from
        email["To"] = smtp_to
        email["Subject"] = "Motor maintenance alert"
        email.set_content(message)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(email)
        return {"sent": True, "detail": "email sent"}
    except Exception as exc:
        return {"sent": False, "detail": str(exc)}


def _summary(report_text: str) -> str:
    lines = [line for line in report_text.splitlines() if line and not line.startswith("#")]
    return "\n".join(lines[:12])
