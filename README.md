# Carson City Trade website

This is the static website source for `carsoncitytrade.com`. It is ready for GitHub Pages deployment with a custom domain.

## What is included

- Option 2-inspired friendly local shop layout
- Carson City Mint / Morgan silver dollar history section
- Live gold and silver spot price board with 10-minute refresh
- Junk silver calculator
- Silver value calculator
- Break-even calculator
- Placeholder contact request form that saves only to this browser's local storage during preview

## Run locally

```bash
cd /home/ubuntu/work/carsoncitytradingpost/site
python3 -m http.server 8088 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8088` on this machine.

## Spot price note

The draft uses `https://api.gold-api.com/price/XAU` and `https://api.gold-api.com/price/XAG` directly from the browser. It falls back to local cached/demo values if the endpoint is unavailable. Before launch, consider moving metal-price fetching to a tiny serverless API route with a paid/contracted provider for reliability and CORS control.
