# Carson contact backend

This directory contains the separate Carson City Trading Post contact-form backend that runs on the VM, not on GitHub Pages.

## Live endpoints
- Public submit URL: `https://carson-contact.35.239.230.32.nip.io/submit`
- Public health URL: `https://carson-contact.35.239.230.32.nip.io/health`

## Purpose
- Accept the website contact-form POST
- Send the email through Gmail API authenticated as `jstanley@sharpkeeper.com`
- Always CC `carsoncity1889@gmail.com`
- Preserve the website success redirect and optional attachment handling

## Files
- `app.py` — FastAPI app
- `carson-contact-backend.service` — systemd unit for the local Uvicorn service on `127.0.0.1:8788`
- `Caddyfile.carson-contact` — Caddy reverse-proxy block that exposes the backend publicly over HTTPS

## Runtime notes
- The backend service runs locally on `127.0.0.1:8788`
- Caddy reverse-proxies the public hostname to that local port
- The recurring form watchdog script lives outside the repo at `~/.hermes/scripts/carson_contact_form_healthcheck.py`
- Backend and watchdog Gmail auth use the isolated Carson token path at `~/.hermes/profiles/carson-gmail-backend/google_token.json`.
- That path is a symlink to the maintained `jstanley@sharpkeeper.com` token at `~/sharpkeeper-outreach/google_workspace_token.json`, so Carson follows token refreshes instead of depending on the mutable default Hermes profile token.

## Anti-spam candidate
See [ROLLOUT.md](ROLLOUT.md) for activation, watchdog migration, backups and rollback. `CARSON_ANTISPAM_DB` selects persistent SQLite storage; `CARSON_TURNSTILE_REQUIRED=1` requires a secret in `CARSON_TURNSTILE_SECRET` and the configured frontend public sitekey. Tests never send real email:

```sh
python -m unittest discover -s backend -p 'test_*.py' -v
```
