# Carson City Trade website

This is the static website source for `carsoncitytrade.com`. It is deployed with GitHub Pages and now uses a backend-style generated price snapshot so the spot board and calculators stay current.

## What is included

- Friendly local shop layout
- Carson City Mint / Morgan silver dollar history section
- Live gold and silver spot price board powered by `data/prices.json`
- Junk silver calculator
- Silver value calculator
- Break-even calculator
- Contact request form that opens the visitor's email app

## Run locally

```bash
cd /home/ubuntu/work/carsoncitytradingpost/site
python3 -m http.server 8088 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8088` on this machine.

## Price snapshot backend

The browser no longer calls metals APIs directly. Instead:

- `scripts/update_prices.py` fetches live spot prices server-side from Swissquote
- it writes `data/prices.json`
- GitHub Actions runs `.github/workflows/update-prices.yml` every 10 minutes
- the frontend reads the generated snapshot and falls back to the last saved copy in `localStorage` if needed

To refresh prices locally:

```bash
cd /home/ubuntu/work/carsoncitytradingpost/site
python3 scripts/update_prices.py
```

## Main Street Market visit page

`visit.html` presents the silent market tour and directions to the two coin showcases at 140 N Main St, Mount Airy, NC. The homepage preview uses a still from the final seconds of the supplied video. The full MP4 loads on demand, preserves portrait framing, has no audio stream, and plays once on request and supports a shortcut to 97 seconds.

The compressed H.264 MP4 and poster images live in `assets/`. `visit.js` handles the visit-page menu and the showcase shortcut. Local-search titles, descriptions, sharing images, location information, VideoObject markup, and the sitemap use the repository's configured domain, `carsoncitytradingpost.com`. The market address and phone were checked against Visit Mayberry's Main Street Market listing; hours are intentionally left to the market to confirm.

For testing the showcase shortcut, use a local server with HTTP byte-range support; Python's basic `http.server` does not support video seeking. GitHub Pages supports byte ranges. Publishing happens only after this branch is merged/deployed. After publishing, verify the new page and media URLs and inspect the page in Google Search Console; local and video search placement is not guaranteed.
