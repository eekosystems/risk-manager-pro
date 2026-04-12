from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.models.notification import NotificationType

_TEMPLATES_DIR = Path(__file__).parent / "html"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


@dataclass(frozen=True)
class DigestItem:
    notification_type: NotificationType
    title: str
    body: str
    resource_type: str
    resource_id: str | None
    created_at: datetime


_SUBJECT_BY_TYPE: dict[NotificationType, str] = {
    NotificationType.CHAT_RESPONSE: "[RMP QA/QC] New AI chat response",
    NotificationType.RISK_CREATED: "[RMP QA/QC] New risk entry created",
    NotificationType.RISK_UPDATED: "[RMP QA/QC] Risk entry updated",
    NotificationType.MITIGATION_CREATED: "[RMP QA/QC] New mitigation created",
    NotificationType.DOCUMENT_INDEXED: "[RMP QA/QC] New document indexed",
}


def _resource_deep_link(resource_type: str, resource_id: str | None) -> str:
    base = settings.app_public_url.rstrip("/") if settings.app_public_url else ""
    if not base or not resource_id:
        return base or ""
    paths = {
        "chat_message": f"/chat?message={resource_id}",
        "risk": f"/risks/{resource_id}",
        "mitigation": f"/mitigations/{resource_id}",
        "document": f"/documents/{resource_id}",
    }
    suffix = paths.get(resource_type, f"/{resource_type}/{resource_id}")
    return urljoin(base + "/", suffix.lstrip("/"))


def _unsubscribe_link(preference_token: str | None) -> str:
    base = settings.app_public_url.rstrip("/") if settings.app_public_url else ""
    if not base or not preference_token:
        return ""
    return f"{base}/notifications/preferences/{preference_token}"


def render_notification(
    *,
    notification_type: NotificationType,
    title: str,
    body: str,
    resource_type: str,
    resource_id: str | None,
    triggered_by_name: str,
    preference_token: str | None,
) -> RenderedEmail:
    deep_link = _resource_deep_link(resource_type, resource_id)
    unsubscribe = _unsubscribe_link(preference_token)
    subject = _SUBJECT_BY_TYPE.get(notification_type, "[RMP QA/QC] Notification")

    context = {
        "title": title,
        "body": body,
        "deep_link": deep_link,
        "unsubscribe_link": unsubscribe,
        "triggered_by_name": triggered_by_name,
        "resource_type": resource_type,
        "notification_type": notification_type.value,
    }

    html = _env.get_template("notification.html").render(**context)
    text = _env.get_template("notification.txt").render(**context)
    return RenderedEmail(subject=subject, html=html, text=text)


def render_digest(
    *,
    items: list[DigestItem],
    period_label: str,
    preference_token: str | None,
) -> RenderedEmail:
    subject = f"[RMP QA/QC] {period_label} digest — {len(items)} item(s)"
    grouped: dict[str, list[DigestItem]] = {}
    for item in items:
        grouped.setdefault(item.notification_type.value, []).append(item)

    enriched = [
        {
            "type": type_key,
            "items": [
                {
                    "title": it.title,
                    "body": it.body,
                    "deep_link": _resource_deep_link(it.resource_type, it.resource_id),
                    "created_at": it.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                }
                for it in group
            ],
        }
        for type_key, group in grouped.items()
    ]
    context = {
        "groups": enriched,
        "period_label": period_label,
        "total": len(items),
        "unsubscribe_link": _unsubscribe_link(preference_token),
    }

    html = _env.get_template("digest.html").render(**context)
    text = _env.get_template("digest.txt").render(**context)
    return RenderedEmail(subject=subject, html=html, text=text)
