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
