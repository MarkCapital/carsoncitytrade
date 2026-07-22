#!/usr/bin/env python3
"""Generate a backend-style metals snapshot for Carson City Trade.

This keeps live spot fetching out of browser JavaScript. The static site reads
``data/prices.json`` generated here by GitHub Actions or local runs.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTFILE = ROOT / 'data' / 'prices.json'
USER_AGENT = 'Mozilla/5.0 (compatible; CarsonCityTrade price updater/1.0; +https://carsoncitytrade.com)'
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 2.0


class UpstreamPriceError(RuntimeError):
    """Raised when the upstream price feed is unavailable or malformed."""


def http_json(url: str) -> Any:
    req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urlopen(req, timeout=20) as response:
        body = response.read().decode('utf-8')
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        preview = body[:200].replace('\n', ' ')
        raise UpstreamPriceError(f'non-JSON response from {url}: {preview!r}') from exc


def parse_swissquote_price(symbol: str, data: Any) -> float:
    try:
        price = float(data[0]['spreadProfilePrices'][0]['ask'])
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise UpstreamPriceError(f'unexpected Swissquote payload for {symbol}: {data!r}') from exc
    if not 5 < price < 10000:
        raise UpstreamPriceError(f'invalid {symbol} price: {price}')
    return price


def fetch_swissquote(symbol: str) -> float:
    url = f'https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/{symbol}/USD'
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            data = http_json(url)
            price = parse_swissquote_price(symbol, data)
            if attempt > 1:
                print(f'{symbol}: recovered on retry {attempt}/{MAX_ATTEMPTS}')
            return price
        except (HTTPError, URLError, TimeoutError, OSError, UpstreamPriceError) as exc:
            last_error = exc
            print(f'{symbol}: attempt {attempt}/{MAX_ATTEMPTS} failed: {exc}')
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS * attempt)
    raise UpstreamPriceError(f'failed to fetch {symbol} after {MAX_ATTEMPTS} attempts: {last_error}')


def build_snapshot() -> dict[str, object]:
    silver = fetch_swissquote('XAG')
    gold = fetch_swissquote('XAU')
    updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    return {
        'updatedAt': updated_at,
        'spot': {
            'silver': round(silver, 4),
            'gold': round(gold, 4),
            'source': 'Swissquote XAG/USD + XAU/USD',
        },
        'notes': [
            'Spot prices are refreshed automatically by GitHub Actions every 10 minutes.',
            'The browser reads this generated snapshot instead of calling metals APIs directly.',
        ],
    }


def main() -> int:
    snapshot = build_snapshot()
    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(json.dumps(snapshot, indent=2) + '\n')
    print(
        f"updated {OUTFILE.relative_to(ROOT)} at {snapshot['updatedAt']} "
        f"from {snapshot['spot']['source']}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
