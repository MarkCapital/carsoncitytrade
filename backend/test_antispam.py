import base64
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
import app
import antispam

class AntiSpamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'CARSON_ANTISPAM_DB': self.tmp.name+'/db', 'CARSON_TURNSTILE_REQUIRED':'1', 'CARSON_TURNSTILE_SECRET':'test-only'})
        self.env.start()
        self.payload = dict(origin=app.ALLOWED_ORIGIN, name='张三', email='customer@example.com', phone='555', reason='Other', message='您好، مرحبا', website='', **{'cf-turnstile-response':'valid'})
        self.client = TestClient(app.APP, client=('198.51.100.2',1234))
        self.send = patch.object(app, 'send_email', return_value={'id':'mock'}).start()
    def tearDown(self):
        patch.stopall(); self.tmp.cleanup()
    def form(self, **changes):
        return {**self.payload, **changes}
    def verification(self, result=None):
        response = MagicMock(); response.read.return_value=json.dumps(result or dict(success=True, hostname='carsoncitytradingpost.com', action='contact')).encode()
        context=MagicMock(); context.__enter__.return_value=response
        return patch.object(antispam,'urlopen',return_value=context)
    def test_missing_and_oversized_tokens(self):
        for token in ['', 'x'*2049]:
            self.assertEqual(self.client.post('/submit',data=self.form(**{'cf-turnstile-response':token})).status_code,400)
        self.send.assert_not_called()
    def test_forged_expired_replayed_wrong_context(self):
        for result in [dict(success=False, **{'error-codes':['invalid-input-response']}),dict(success=False, **{'error-codes':['timeout-or-duplicate']}),dict(success=True,hostname='evil.example',action='contact'),dict(success=True,hostname='carsoncitytradingpost.com',action='login')]:
            with self.verification(result):
                self.assertEqual(self.client.post('/submit',data=self.form()).status_code,400)
        self.send.assert_not_called()
    def test_valid_multilingual_attachment_and_duplicate(self):
        with self.verification():
            response=self.client.post('/submit',data=self.form(attachments_json=json.dumps([dict(name='coin.txt',type='text/plain',base64=base64.b64encode(b'coin').decode())])))
            self.assertEqual(response.status_code,200)
            self.assertEqual(self.send.call_args.args[1][0][2],b'coin')
            self.assertEqual(self.send.call_args.args[0]['message'],'您好، مرحبا')
            self.assertEqual(self.client.post('/submit',data=self.form()).status_code,400)
            self.assertEqual(self.send.call_count,1)
    def test_public_dry_run_cannot_send_or_bypass_real_submit(self):
        response=self.client.post('/submit',json=self.form(dryRun=True))
        self.assertEqual(response.status_code,200); self.send.assert_not_called()
        self.assertEqual(self.client.post('/submit',json=self.form()).status_code,400)
    def test_loopback_monitor_and_forwarded_localhost(self):
        local=TestClient(app.APP,client=('127.0.0.1',1234))
        self.assertEqual(local.post('/submit',data=self.form(**{'cf-turnstile-response':''})).status_code,200)
        self.assertEqual(local.post('/submit',headers={'X-Forwarded-For':'127.0.0.1'},data=self.form(**{'cf-turnstile-response':''})).status_code,400)
        self.assertEqual(self.send.call_count,1)
    def test_failure_is_closed_health_remains_available(self):
        with patch.object(antispam,'urlopen',side_effect=TimeoutError('secret-never-exposed')):
            response=self.client.post('/submit',data=self.form())
            self.assertEqual(response.status_code,400); self.assertNotIn('secret-never-exposed',response.text)
        self.assertEqual(self.client.get('/health').status_code,200);self.send.assert_not_called()
    def test_delivery_failure_releases_reservation(self):
        with self.verification():
            self.send.side_effect=RuntimeError('credentials-not-exposed')
            self.assertEqual(self.client.post('/submit',data=self.form()).status_code,400)
            self.send.side_effect=None
            self.assertEqual(self.client.post('/submit',data=self.form()).status_code,200)
    def test_sender_persists_across_ip_phone_message_and_instances(self):
        for i in range(3):
            antispam.Store().reserve(str(i),'CUSTOMER@example.com',str(i),now=100000+i*4000)
        with self.assertRaises(ValueError):
            antispam.Store().reserve('new-ip','customer@example.com','new-message',now=113000)
        self.assertTrue(antispam.Store().reserve('new-ip','customer@example.com','new-message',now=200000))
    def test_concurrent_reservations_atomic(self):
        store=antispam.Store();store.connect().close()
        def reserve(i):
            try: return bool(store.reserve('same-ip',str(i)+'@example.com',str(i)))
            except ValueError: return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(reserve,range(8))),2)
    def test_referer_prefix_attack(self):
        self.assertEqual(self.client.post('/submit',headers={'Referer':app.ALLOWED_ORIGIN+'.evil.example/'},data=self.form()).status_code,400)
        self.send.assert_not_called()
    def test_uvicorn_proxy_headers_cannot_exempt_public_request(self):
        from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
        proxy = TestClient(ProxyHeadersMiddleware(app.APP, trusted_hosts=['127.0.0.1']), client=('127.0.0.1',1234))
        with self.verification() as verify:
            self.assertEqual(proxy.post('/submit', headers={'X-Forwarded-For':'198.51.100.9'}, data=self.form()).status_code,200)
            body=verify.call_args.args[0].data.decode()
            self.assertIn('remoteip=198.51.100.9',body)
        self.assertEqual(proxy.post('/submit',headers={'X-Forwarded-For':'127.0.0.1'},data=self.form(**{'cf-turnstile-response':''})).status_code,400)
    def test_weekly_quota_and_empty_email(self):
        for i in range(6):
            antispam.Store().reserve(str(i),'customer@example.com',str(i),now=100000+i*30000)
        with self.assertRaises(ValueError):
            antispam.Store().reserve('new','customer@example.com','new',now=280000)
        for i in range(8):
            self.assertTrue(antispam.Store().reserve('empty'+str(i),'','empty'+str(i),now=280000))
    def test_missing_secret_rejects_without_network(self):
        with patch.dict(os.environ,{'CARSON_TURNSTILE_SECRET':''}), patch.object(antispam,'urlopen') as verify:
            self.assertEqual(self.client.post('/submit',data=self.form()).status_code,400)
            verify.assert_not_called()
        self.send.assert_not_called()
    def test_release_closes_connection_on_success_and_failure(self):
        for failure in [False, True]:
            db = MagicMock()
            if failure: db.execute.side_effect=OSError('storage failure')
            with patch.object(antispam.Store,'connect',return_value=db):
                if failure:
                    with self.assertRaises(OSError): antispam.Store().release('reservation')
                else: antispam.Store().release('reservation')
            db.close.assert_called_once()
    def test_schema_failure_closes_connection(self):
        db=MagicMock();db.execute.side_effect=OSError('schema failure')
        with patch.object(antispam.sqlite3,'connect',return_value=db):
            with self.assertRaises(OSError): antispam.Store().connect()
        db.close.assert_called_once()
    def test_delivery_and_release_failure_sanitized(self):
        with self.verification(), patch.object(antispam.Store,'release',side_effect=OSError('private-db-path')):
            self.send.side_effect=RuntimeError('private-gmail-token')
            response=self.client.post('/submit',data=self.form())
        self.assertEqual(response.status_code,400)
        self.assertNotIn('private-db-path',response.text)
        self.assertNotIn('private-gmail-token',response.text)
        with antispam.Store().connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM submissions').fetchone()[0],1)
    def test_body_limit_before_parsing_or_decoding(self):
        with patch.object(app,'MAX_REQUEST_BYTES',100), patch.object(app,'normalize_attachments') as decode:
            for headers in [{}, {'Content-Length':'1'}, {'Content-Length':'101'}, {'Content-Length':'invalid'}]:
                response=self.client.post('/submit',content=b'x'*101,headers=headers)
                self.assertEqual(response.status_code,400)
            decode.assert_not_called()
        self.send.assert_not_called()
    def test_chunked_body_limit(self):
        import asyncio
        from starlette.requests import Request
        chunks=iter([dict(type='http.request',body=b'x'*60,more_body=True),dict(type='http.request',body=b'x'*60,more_body=False)])
        async def receive(): return next(chunks)
        request=Request(dict(type='http',method='POST',path='/submit',headers=[],client=('198.51.100.1',1234)),receive)
        with patch.object(app,'MAX_REQUEST_BYTES',100), patch.object(app,'normalize_attachments') as decode:
            response=asyncio.run(app.submit(request))
            self.assertEqual(response.status_code,400)
            decode.assert_not_called()
    def test_large_multipart_attachment_preserves_documented_limit(self):
        raw=b'x'*(1024*1024)
        fields=self.form(attachments_json=json.dumps([dict(name='coin.jpg',type='image/jpeg',base64=base64.b64encode(raw).decode())]))
        with self.verification():
            response=self.client.post('/submit',files={key:(None,value) for key,value in fields.items()})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.send.call_args.args[1][0][2],raw)
    def test_full_attachment_limit_and_over_limit(self):
        for size, expected in [(app.MAX_ATTACHMENT_BYTES,200),(app.MAX_ATTACHMENT_BYTES+1,400)]:
            raw=b'x'*size
            fields=self.form(message=str(size),attachments_json=json.dumps([dict(name='coin.jpg',type='image/jpeg',base64=base64.b64encode(raw).decode())]))
            with self.verification():
                response=self.client.post('/submit',files={key:(None,value) for key,value in fields.items()})
            self.assertEqual(response.status_code,expected)
        self.assertEqual(self.send.call_count,1)
    def test_db_failure_does_not_send(self):
        with self.verification(), patch.object(antispam.Store,'connect',side_effect=OSError('private-path')):
            response=self.client.post('/submit',data=self.form())
            self.assertEqual(response.status_code,400); self.assertNotIn('private-path',response.text)
        self.send.assert_not_called()

if __name__=='__main__': unittest.main()
