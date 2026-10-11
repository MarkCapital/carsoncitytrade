"""Persistent admission control; contains no Gmail or application secrets."""
import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def verify_token(token, remoteip):
    secret = os.environ.get('CARSON_TURNSTILE_SECRET', '')
    if not secret:
        raise ValueError('Verification is temporarily unavailable. Please email us directly.')
    if not isinstance(token, str) or not token or len(token) > 2048:
        raise ValueError('Please complete the verification and try again.')
    try:
        request = Request('https://challenges.cloudflare.com/turnstile/v0/siteverify',
                          data=urlencode({'secret': secret, 'response': token, 'remoteip': remoteip}).encode())
        with urlopen(request, timeout=8) as response:
            result = json.loads(response.read(65536))
    except Exception:
        raise ValueError('Verification is temporarily unavailable. Please try again.') from None
    if (result.get('success') is not True
            or result.get('hostname') != 'carsoncitytradingpost.com'
            or result.get('action') != 'contact'):
        raise ValueError('Verification failed or expired. Please try again.')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest() if value else ''


class Store:
    def __init__(self, path=None):
        self.path = path or os.environ.get('CARSON_ANTISPAM_DB', str(Path(__file__).parent / 'state' / 'antispam.sqlite3'))

    def connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(self.path, timeout=2)
        try:
            db.execute('CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, ts REAL, ip TEXT, email TEXT, duplicate TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS submissions_ts ON submissions(ts)')
            return db
        except Exception:
            db.close()
            raise

    def reserve(self, host, email, duplicate, now=None):
        now = time.time() if now is None else now
        ip, email, duplicate = map(digest, (host, email.casefold(), duplicate))
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM submissions WHERE ts < ?', (now - 7 * 86400,))
            limits = [('ip', ip, 600, 2), ('email', email, 86400, 3), ('email', email, 7 * 86400, 6), ('duplicate', duplicate, 21600, 1)]
            for column, key, window, maximum in limits:
                if key and db.execute(f'SELECT count(*) FROM submissions WHERE {column}=? AND ts>=?', (key, now-window)).fetchone()[0] >= maximum:
                    raise ValueError('Please wait before sending another inquiry, or email us directly.')
            reservation = uuid.uuid4().hex
            db.execute('INSERT INTO submissions VALUES (?,?,?,?,?)', (reservation, now, ip, email, duplicate))
            db.commit()
            return reservation
        finally:
            db.close()

    def release(self, reservation):
        db = self.connect()
        try:
            with db:
                db.execute('DELETE FROM submissions WHERE id=?', (reservation,))
        finally:
            db.close()
