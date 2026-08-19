from __future__ import annotations

import base64
import json
import os
import secrets
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

APP = FastAPI()
app = APP

ALLOWED_ORIGIN = 'https://carsoncitytradingpost.com'
PRIMARY_TO = 'jstanley@sharpkeeper.com'
CC_TO = 'carsoncity1889@gmail.com'
SUCCESS_URL = 'https://carsoncitytradingpost.com/?contact=success#contact'
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS = 5
HERMES_HOME = Path(os.environ.get('HERMES_HOME', str(Path.home() / '.hermes')))
GOOGLE_TOKEN = HERMES_HOME / 'google_token.json'
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic',
    'https://www.googleapis.com/auth/gmail.settings.sharing',
]


def load_gmail_service():
    creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN), GOOGLE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        GOOGLE_TOKEN.write_text(creds.to_json())
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


def normalize_attachments(raw_attachments: list[dict[str, Any]] | None):
    attachments = raw_attachments or []
    if len(attachments) > MAX_ATTACHMENTS:
        raise ValueError('Too many attachments.')
    total_bytes = 0
    normalized = []
    for item in attachments:
        base64_data = str(item.get('base64') or '').strip()
        if not base64_data:
            continue
        filename = str(item.get('name') or 'attachment').strip() or 'attachment'
        mime_type = str(item.get('type') or 'application/octet-stream').strip() or 'application/octet-stream'
        raw_bytes = base64.b64decode(base64_data)
        total_bytes += len(raw_bytes)
        normalized.append((filename, mime_type, raw_bytes))
    if total_bytes > MAX_ATTACHMENT_BYTES:
        raise ValueError('Attachments exceed 10MB total limit.')
    return normalized, total_bytes


def build_message(payload: dict[str, Any], attachments: list[tuple[str, str, bytes]]) -> str:
    subject = 'Carson City Trading Post website inquiry'
    reason = str(payload.get('reason') or '').strip()
    if reason:
        subject += f' — {reason}'

    email = EmailMessage()
    email['To'] = PRIMARY_TO
    email['Cc'] = CC_TO
    email['Subject'] = subject
    email['From'] = PRIMARY_TO
    reply_to = str(payload.get('email') or '').strip()
    if reply_to:
        email['Reply-To'] = reply_to

    text_lines = [
        'New Carson City Trading Post website inquiry',
        '',
        f"Name: {str(payload.get('name') or '').strip()}",
        f"Email: {reply_to or '(not provided)'}",
        f"Phone: {str(payload.get('phone') or '').strip() or '(not provided)'}",
        f"Reason: {reason or '(not provided)'}",
        '',
        'Message:',
        str(payload.get('message') or '').strip(),
    ]
    email.set_content('\n'.join(text_lines))
    html_body = '<br>'.join(line if line else '&nbsp;' for line in [
        'New Carson City Trading Post website inquiry',
        '',
        f"Name: {str(payload.get('name') or '').strip()}",
        f"Email: {reply_to or '(not provided)'}",
        f"Phone: {str(payload.get('phone') or '').strip() or '(not provided)'}",
        f"Reason: {reason or '(not provided)'}",
        '',
        'Message:',
        str(payload.get('message') or '').strip(),
    ])
    email.add_alternative(f'<html><body>{html_body}</body></html>', subtype='html')

    for filename, mime_type, raw_bytes in attachments:
        maintype, subtype = (mime_type.split('/', 1) + ['octet-stream'])[:2]
        email.add_attachment(raw_bytes, maintype=maintype, subtype=subtype, filename=filename)

    return base64.urlsafe_b64encode(email.as_bytes()).decode('utf-8')


def send_email(payload: dict[str, Any], attachments: list[tuple[str, str, bytes]]):
    service = load_gmail_service()
    raw_message = build_message(payload, attachments)
    return service.users().messages().send(userId='me', body={'raw': raw_message}).execute()


def validate_payload(payload: dict[str, Any]):
    origin = str(payload.get('origin') or '').strip()
    if origin != ALLOWED_ORIGIN:
        raise ValueError('Origin not allowed.')
    if not str(payload.get('name') or '').strip():
        raise ValueError('Name is required.')
    if not str(payload.get('message') or '').strip():
        raise ValueError('Message is required.')


def success_html(target_url: str):
    return HTMLResponse(
        f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Thanks</title></head>
<body>
  <p>Thanks — your request was sent directly to Carson City Trading Post.</p>
  <p><a href="{target_url}">Continue</a></p>
  <script>window.top.location.href = {json.dumps(target_url)};</script>
</body></html>'''
    )


def error_html(message: str, target_url: str):
    return HTMLResponse(
        f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Error</title></head>
<body>
  <p>There was a problem sending your request.</p>
  <p>{message}</p>
  <p>Please email <a href="mailto:{CC_TO}">{CC_TO}</a> directly.</p>
  <p><a href="{target_url}">Return to Carson City Trading Post</a></p>
</body></html>''',
        status_code=400,
    )


def parse_form_payload(form):
    attachments_json = form.get('attachments_json') or '[]'
    payload = {
        'origin': form.get('origin') or '',
        'redirect': form.get('redirect') or SUCCESS_URL,
        'name': form.get('name') or '',
        'email': form.get('email') or '',
        'phone': form.get('phone') or '',
        'reason': form.get('reason') or '',
        'message': form.get('message') or '',
        'dryRun': str(form.get('dryRun') or '').lower() == 'true',
        'attachments': json.loads(attachments_json),
    }
    return payload


@APP.get('/health')
async def health():
    return {
        'ok': True,
        'service': 'carson-contact-backend',
        'primaryTo': PRIMARY_TO,
        'ccTo': CC_TO,
    }


@APP.get('/')
async def index():
    return {'ok': True, 'service': 'carson-contact-backend'}


@APP.post('/submit')
async def submit(request: Request):
    content_type = request.headers.get('content-type', '').lower()
    wants_json = 'application/json' in content_type
    target_url = SUCCESS_URL
    try:
        if wants_json:
            payload = await request.json()
        else:
            form = await request.form()
            payload = parse_form_payload(form)
            target_url = str(payload.get('redirect') or SUCCESS_URL).strip() or SUCCESS_URL
        validate_payload(payload)
        attachments, total_bytes = normalize_attachments(payload.get('attachments'))
        if payload.get('dryRun') is True:
            body = {'ok': True, 'dryRun': True, 'attachmentCount': len(attachments), 'totalBytes': total_bytes}
            return JSONResponse(body)
        result = send_email(payload, attachments)
        body = {
            'ok': True,
            'sent': True,
            'id': result.get('id'),
            'threadId': result.get('threadId'),
            'attachmentCount': len(attachments),
            'totalBytes': total_bytes,
        }
        if wants_json:
            return JSONResponse(body)
        return success_html(target_url)
    except Exception as exc:
        message = str(exc) or 'Unknown error'
        if wants_json:
            return JSONResponse({'ok': False, 'error': message}, status_code=400)
        return error_html(message, target_url)
