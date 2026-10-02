from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import app


class _CredentialsStub:
    def to_json(self) -> str:
        return '{"refreshed": true}'


class RefreshedCredentialPersistenceTests(unittest.TestCase):
    def test_read_only_managed_token_does_not_break_refreshed_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            token = Path(temp_dir) / 'google_token.json'
            token.write_text('{"managed": true}')
            token.chmod(0o400)
            try:
                app.save_refreshed_credentials(_CredentialsStub(), token)
                self.assertEqual(token.read_text(), '{"managed": true}')
            finally:
                token.chmod(0o600)


if __name__ == '__main__':
    unittest.main()
