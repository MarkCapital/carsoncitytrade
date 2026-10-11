from __future__ import annotations

import base64
import html
import json
import os
import re
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from antispam import Store, verify_token
from starlette.concurrency import run_in_threadpool
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
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
# Covers base64 plus worst-case URL encoding and normal multipart overhead.
MAX_REQUEST_BYTES = 48 * 1024 * 1024
ALLOWED_REASONS = {
    'Appraisal request',
    'I am interested in rare coins for sale',
    'Question about weekly specials',
    'I am interested in investing in gold or silver coins',
    'Question about Morgan silver dollars',
    'Other',
    'Website contact form test',
}
LOCALHOSTS = {'127.0.0.1', '::1', 'localhost'}
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
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
        # this service. The refreshed in-memory credential is still usable.
        pass


def load_gmail_service():
    creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN), GOOGLE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        save_refreshed_credentials(creds)
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


def normalize_text(value: Any) -> str:
    return ' '.join(str(value or '').split()).strip()


def internal_request(request: Request) -> bool:
    # Caddy always supplies X-Forwarded-For. Never exempt a proxied request.
    return client_host(request) in LOCALHOSTS and not request.headers.get("x-forwarded-for")


def client_host(request: Request) -> str:
    return str((request.client.host if request.client else '') or '').strip()


def build_duplicate_key(request: Request, payload: dict[str, Any]) -> str:
    host = client_host(request)
    reason = normalize_text(payload.get('reason')).lower()
    message = normalize_text(payload.get('message')).lower()
    phone = normalize_text(payload.get('phone'))
    email_address = normalize_text(payload.get('email')).lower()

    contact_key = ''
    if phone:
        contact_key = f'phone:{phone}'
    elif email_address:
        contact_key = f'email:{email_address}'

    return '||'.join(part for part in [host, reason, message, contact_key] if part)


def validate_request_context(request: Request, payload: dict[str, Any], wants_json: bool):
    header_origin = normalize_text(request.headers.get('origin'))
    if header_origin and header_origin != ALLOWED_ORIGIN:
        raise ValueError('Origin header not allowed.')

    referer = normalize_text(request.headers.get('referer'))
    if referer and (urlsplit(referer).scheme + '://' + urlsplit(referer).netloc) != ALLOWED_ORIGIN:
        raise ValueError('Referer not allowed.')

    if wants_json and payload.get('dryRun') is not True and not internal_request(request):
        raise ValueError('JSON submissions are not allowed from public clients.')


def build_message(payload: dict[str, Any], attachments: list[tuple[str, str, bytes]]) -> str:
    subject = 'Carson City Trading Post website inquiry'
    reason = normalize_text(payload.get('reason'))
    if reason:
        subject += f' — {reason}'

    email = EmailMessage()
    email['To'] = PRIMARY_TO
    email['Cc'] = CC_TO
    email['Subject'] = subject
    email['From'] = PRIMARY_TO
    reply_to = normalize_text(payload.get('email'))
    if reply_to:
        email['Reply-To'] = reply_to

    name = normalize_text(payload.get('name'))
    phone = normalize_text(payload.get('phone'))
    message = normalize_text(payload.get('message'))

    text_lines = [
        'New Carson City Trading Post website inquiry',
        '',
        f"Name: {name}",
        f"Email: {reply_to or '(not provided)'}",
        f"Phone: {phone or '(not provided)'}",
        f"Reason: {reason or '(not provided)'}",
        '',
        'Message:',
        message,
    ]
    email.set_content('\n'.join(text_lines))
    html_body = '<br>'.join(line if line else '&nbsp;' for line in [
        'New Carson City Trading Post website inquiry',
        '',
        f"Name: {html.escape(name)}",
        f"Email: {html.escape(reply_to or '(not provided)')}",
        f"Phone: {html.escape(phone or '(not provided)')}",
        f"Reason: {html.escape(reason or '(not provided)')}",
        '',
        'Message:',
        html.escape(message),
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
    origin = normalize_text(payload.get('origin'))
    if origin != ALLOWED_ORIGIN:
        raise ValueError('Origin not allowed.')
    if normalize_text(payload.get('website')):
        raise ValueError('Request blocked.')

    name = normalize_text(payload.get('name'))
    if not name:
        raise ValueError('Name is required.')

    message = normalize_text(payload.get('message'))
    if not message:
        raise ValueError('Message is required.')

    reason = normalize_text(payload.get('reason'))
    if reason not in ALLOWED_REASONS:
        raise ValueError('Reason is invalid.')

    email_address = normalize_text(payload.get('email'))
    if email_address and not EMAIL_PATTERN.fullmatch(email_address):
        raise ValueError('Email is invalid.')


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
  <p>{html.escape(message)}</p>
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
        'website': form.get('website') or '',
        'name': form.get('name') or '',
        'email': form.get('email') or '',
        'phone': form.get('phone') or '',
        'reason': form.get('reason') or '',
        'message': form.get('message') or '',
        'dryRun': str(form.get('dryRun') or '').lower() == 'true',
        'cf-turnstile-response': form.get('cf-turnstile-response') or '',
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
        # Bound bytes even when Content-Length is absent or false. Reuse the
        # bounded body for Starlette's JSON/multipart parser.
        length = request.headers.get('content-length')
        if length and (not length.isdigit() or int(length) > MAX_REQUEST_BYTES):
            raise ValueError('Request exceeds the form size limit.')
        chunks = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                raise ValueError('Request exceeds the form size limit.')
            chunks.append(chunk)
        request._body = b''.join(chunks)
        del chunks
        if wants_json:
            payload = await request.json()
        else:
            form = await request.form(max_files=MAX_ATTACHMENTS, max_fields=20, max_part_size=MAX_REQUEST_BYTES)
            payload = parse_form_payload(form)
            target_url = SUCCESS_URL
        validate_request_context(request, payload, wants_json)
        validate_payload(payload)
        attachments, total_bytes = normalize_attachments(payload.get('attachments'))
        if payload.get('dryRun') is True:
            body = {'ok': True, 'dryRun': True, 'attachmentCount': len(attachments), 'totalBytes': total_bytes}
            return JSONResponse(body)
        reservation = None
        if not internal_request(request):
            if os.environ.get('CARSON_TURNSTILE_REQUIRED') == '1':
                await run_in_threadpool(verify_token, payload.get('cf-turnstile-response'), client_host(request))
            try:
                reservation = await run_in_threadpool(Store().reserve, client_host(request),
                    normalize_text(payload.get('email')), build_duplicate_key(request, payload))
            except ValueError:
                raise
            except Exception:
                raise ValueError('Submission is temporarily unavailable. Please email us directly.') from None
        try:
            result = await run_in_threadpool(send_email, payload, attachments)
        except Exception:
            if reservation:
                try:
                    await run_in_threadpool(Store().release, reservation)
                except Exception:
                    # Keep the reservation conservatively; never expose storage details.
                    pass
            raise ValueError('Delivery is temporarily unavailable. Please email us directly.') from None
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
