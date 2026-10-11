#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SITE_URL = 'https://carsoncitytradingpost.com/'
BACKEND_ENDPOINT = 'https://carson-contact.35.239.230.32.nip.io/submit'
BACKEND_HEALTH = 'https://carson-contact.35.239.230.32.nip.io/health'
OLD_BACKEND_MARKERS = [
    'formsubmit.co',
    'script.google.com/macros/s/',
]
VERIFY_INBOX_TO = 'jstanley@sharpkeeper.com'
EXPECTED_CC = 'carsoncity1889@gmail.com'
ATTACHMENT_NAME = 'carson-form-healthcheck.txt'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Hermes Carson form health check)'}
ET = ZoneInfo('America/New_York')
HERMES_HOME = Path(os.environ.get('HERMES_HOME', str(Path.home() / '.hermes')))
GOOGLE_TOKEN = Path(
    os.environ.get(
        'CARSON_GOOGLE_TOKEN_PATH',
        str(HERMES_HOME / 'profiles' / 'carson-gmail-backend' / 'google_token.json'),
    )
)
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic',
    'https://www.googleapis.com/auth/gmail.settings.sharing',
]


def save_refreshed_credentials(creds, token_path: Path = GOOGLE_TOKEN):
    """Persist refreshed credentials when the managed token is writable."""
    try:
        token_path.write_text(creds.to_json())
    except PermissionError:
        # The production token is intentionally root-managed and read-only to
        # this job. The refreshed in-memory credential is still usable.
        pass


def gmail_service():
    creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN), GOOGLE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        save_refreshed_credentials(creds)
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


def fetch_text(url: str) -> tuple[int, str]:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=45) as resp:
        status = getattr(resp, 'status', resp.getcode())
        body = resp.read().decode('utf-8', 'replace')
        return status, body


def fetch_json(url: str) -> tuple[int, dict]:
    status, body = fetch_text(url)
    return status, json.loads(body)


def build_multipart(fields: list[tuple[str, str]]) -> tuple[str, bytes]:
    boundary = f'----HermesBoundary{uuid.uuid4().hex}'
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.extend(
            [
                f'--{boundary}\r\n'.encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode('utf-8'),
                b'\r\n',
            ]
        )
    chunks.append(f'--{boundary}--\r\n'.encode())
    return boundary, b''.join(chunks)


def submit_test(now_et: datetime, marker: str) -> tuple[int, str]:
    attachment_payload = [
        {
            'name': ATTACHMENT_NAME,
            'type': 'text/plain',
            'base64': base64.b64encode(
                f'Scheduled Carson City Trading Post form health check at {now_et.isoformat()}\nmarker={marker}\n'.encode('utf-8')
            ).decode('ascii'),
        }
    ]
    fields = [
        ('origin', 'https://carsoncitytradingpost.com'),
        ('redirect', 'https://carsoncitytradingpost.com/?contact=success#contact'),
        ('attachments_json', json.dumps(attachment_payload)),
        ('name', 'Hermes scheduled form health check'),
        ('email', 'noreply@example.com'),
        ('phone', ''),
        ('reason', 'Website contact form test'),
        (
            'message',
            'Automated scheduled Carson City Trading Post contact-form health check at '
            f'{now_et.isoformat()} with marker {marker}. '
            'This is a real end-to-end test submission with attachment. Please ignore.',
        ),
    ]
    boundary, body = build_multipart(fields)
    req = Request(
        'http://127.0.0.1:8788/submit',
        data=body,
        headers={
            **HEADERS,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Origin': 'https://carsoncitytradingpost.com',
            'Referer': 'https://carsoncitytradingpost.com/',
            'Content-Type': f'multipart/form-data; boundary={boundary}',
        },
        method='POST',
    )
    try:
        with urlopen(req, timeout=60) as resp:
            status = getattr(resp, 'status', resp.getcode())
            text = resp.read().decode('utf-8', 'replace')
            return status, text
    except HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')


def gmail_search(query: str, max_results: int = 10) -> list[dict]:
    service = gmail_service()
    result = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    return result.get('messages', [])


def decode_part_body(part: dict) -> str:
    data = (((part or {}).get('body') or {}).get('data') or '')
    if not data:
        return ''
    padding = '=' * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode((data + padding).encode('ascii')).decode('utf-8', 'replace')
    except Exception:
        return ''


def walk_parts(part: dict):
    yield part
    for child in (part or {}).get('parts', []) or []:
        yield from walk_parts(child)


def gmail_get(message_id: str) -> dict:
    service = gmail_service()
    msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
    payload = msg.get('payload', {})
    headers = {h.get('name', '').lower(): h.get('value', '') for h in payload.get('headers', [])}
    text_parts = []
    attachments = []
    for part in walk_parts(payload):
        filename = part.get('filename') or ''
        if filename:
            attachments.append(filename)
        mime_type = part.get('mimeType') or ''
        if mime_type.startswith('text/plain'):
            text = decode_part_body(part)
            if text:
                text_parts.append(text)
    body = '\n'.join(text_parts)
    return {
        'id': msg.get('id'),
        'threadId': msg.get('threadId'),
        'labels': msg.get('labelIds', []),
        'from': headers.get('from', ''),
        'to': headers.get('to', ''),
        'cc': headers.get('cc', ''),
        'subject': headers.get('subject', ''),
        'date': headers.get('date', ''),
        'body': body,
        'attachments': attachments,
    }


def wait_for_inbox_arrival(marker: str, timeout_s: int = 120, poll_s: int = 5) -> dict:
    query = f'from:jstanley@sharpkeeper.com to:{VERIFY_INBOX_TO} newer_than:1d "{marker}"'
    deadline = time.time() + timeout_s
    last_hits: list[dict] = []
    while time.time() < deadline:
        hits = gmail_search(query, max_results=10)
        last_hits = hits
        for hit in hits:
            msg = gmail_get(hit['id'])
            if 'INBOX' not in msg.get('labels', []):
                continue
            if marker not in msg.get('body', ''):
                continue
            if VERIFY_INBOX_TO not in msg.get('to', ''):
                continue
            if 'jstanley@sharpkeeper.com' not in msg.get('from', ''):
                continue
            if EXPECTED_CC not in msg.get('cc', ''):
                continue
            if ATTACHMENT_NAME not in msg.get('attachments', []):
                continue
            return msg
        time.sleep(poll_s)
    raise TimeoutError(f'Timed out waiting for Gmail arrival for marker {marker}. Last hit count: {len(last_hits)}')


def main() -> int:
    now_et = datetime.now(ET)

    # Two UTC cron slots are used to survive DST changes. Only the one that
    # lands at 10am America/New_York should emit output.
    force_run = os.environ.get('CARSON_FORM_HEALTHCHECK_FORCE_RUN') == '1'
    if now_et.hour != 10 and not force_run:
        return 0

    marker = f'carson-watch-{now_et.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:8]}'
    errors: list[str] = []

    status, health = fetch_json(BACKEND_HEALTH)
    if status != 200:
        errors.append(f'backend health returned HTTP {status}')
    if health.get('primaryTo') != VERIFY_INBOX_TO:
        errors.append('backend health primaryTo does not match jstanley@sharpkeeper.com')
    if health.get('ccTo') != EXPECTED_CC:
        errors.append('backend health ccTo does not match carsoncity1889@gmail.com')

    status, html = fetch_text(SITE_URL)
    if status != 200:
        errors.append(f'homepage returned HTTP {status}')
    if f'action="{BACKEND_ENDPOINT}"' not in html:
        errors.append('live homepage is missing the direct backend form action')
    for old_marker in OLD_BACKEND_MARKERS:
        if old_marker in html:
            errors.append(f'live homepage still contains old backend marker: {old_marker}')

    app_js_url = None
    marker_token = 'src="./app.js?v='
    idx = html.find(marker_token)
    if idx == -1:
        errors.append('homepage is missing the app.js script tag')
        js = ''
    else:
        start = idx + len('src="')
        end = html.find('"', start)
        app_js_url = urljoin(SITE_URL, html[start:end])
        status, js = fetch_text(app_js_url)
        if status != 200:
            errors.append(f'app.js returned HTTP {status}')
    if BACKEND_ENDPOINT not in js:
        errors.append('live app.js is missing the direct backend endpoint')
    for old_marker in OLD_BACKEND_MARKERS:
        if old_marker in js:
            errors.append(f'live app.js still contains old backend marker: {old_marker}')

    if errors:
        raise SystemExit('Carson City Trading Post contact-form health check FAILED:\n- ' + '\n- '.join(errors))

    submit_status, submit_text = submit_test(now_et, marker)
    if submit_status != 200:
        raise SystemExit(
            f'Carson City Trading Post contact-form health check FAILED: backend returned HTTP {submit_status}: '
            + submit_text[:500]
        )
    if 'Thanks — your request was sent directly to Carson City Trading Post.' not in submit_text:
        raise SystemExit(
            'Carson City Trading Post contact-form health check FAILED: direct backend did not confirm success: '
            + submit_text[:500]
        )

    try:
        delivered_message = wait_for_inbox_arrival(marker)
    except Exception as exc:
        raise SystemExit(
            'Carson City Trading Post contact-form health check FAILED: submission succeeded but no matching Gmail delivery was verified in '
            f'{VERIFY_INBOX_TO}: {exc}'
        ) from exc

    print(
        'Carson City Trading Post contact form check passed. '
        f'Time: {now_et.strftime("%Y-%m-%d %I:%M %p %Z")}. '
        'Verified live homepage wiring, live app.js wiring, public backend health, public form submission, '
        f'and Gmail inbox arrival in {VERIFY_INBOX_TO} with CC {EXPECTED_CC} and attachment {ATTACHMENT_NAME} at '
        f'{delivered_message.get("date", "unknown time")}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
