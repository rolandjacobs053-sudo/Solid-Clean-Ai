import ipaddress
import logging
import os
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
VALID_EMAIL = re.compile(r"^[^@\s\[\]]+@[^@\s\[\]]+\.[A-Za-z]{2,}$")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


def render_html(brand: str, body: str, link: tuple | None = None) -> str:
    text = escape(body).replace("\n", "<br>")
    button = ""
    if link:
        button = (f'<p style="margin:24px 0"><a href="{escape(link[1])}" style="background:#023F00;color:#ffffff;padding:12px 22px;'
                  f'border-radius:999px;text-decoration:none;font-weight:bold">{escape(link[0])}</a></p>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f7f9"><tr><td align="center" style="padding:24px">'
            f'<table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border-radius:12px"><tr><td style="padding:28px;font-family:Arial,sans-serif;font-size:15px;line-height:1.55;color:#1e293b">'
            f'<p style="margin:0 0 18px;font-size:18px;font-weight:bold;color:#023F00">{escape(brand)}</p>{text}{button}'
            f'<p style="margin-top:28px;font-size:12px;color:#94a3b8">Sent by {escape(brand)}. We never ask for your password or card details by email.</p>'
            f'</td></tr></table></td></tr></table>')


async def send_email(*, to: str, subject: str, html: str, from_name: str = "", reply_to: str = "") -> str:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": from_name or EMAIL_FROM_NAME}
    if reply_to:
        payload["contact_email"] = reply_to
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return "sent"
    except httpx.HTTPStatusError as e:
        try:
            info = e.response.json()
        except ValueError:
            info = {}
        if info.get("code") in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning("Email paused: %s (%s): %s", info.get("code"), e.response.status_code, info.get("message", ""))
            return "paused"
        logger.error("Email send failed: %s %s", e.response.status_code, e.response.text)
        return "failed"
    except Exception:
        logger.exception("Email send error")
        return "failed"
