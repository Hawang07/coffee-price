# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Coffee gear price tracker for the Thai market, monetised via affiliate commissions. Crawls prices daily, stores history, and will serve SEO-optimised product pages. Target products: 4,000–10,000 THB grinders (Shopee commission cap of 225 THB/order is reached at ~7,500 THB; expensive espresso machines earn the same commission as mid-range grinders but convert far worse).

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# One-time seed (9 starter products)
python -m app.seed

# Run crawler manually (fetches prices → PriceSnapshot → PriceDaily rollup)
python -m app.crawler.runner
```

No test suite yet. No build step (frontend is plain HTML/CSS + HTMX + Chart.js via CDN).

## Architecture

### Data flow

```
AffiliateProvider.fetch_prices()
  → PriceSnapshot (append-only raw log)
    → rollup_today() → PriceDaily (min/max per listing per day, for fast chart queries)
```

`Listing.fail_streak` increments each missed crawl; at `LISTING_FAIL_THRESHOLD` (default 7) the listing is soft-deleted (`active = False`).

### Key modules

| File | Role |
|---|---|
| `app/config.py` | All env vars + `expected_commission(price)` helper |
| `app/clock.py` | Single `utcnow()` — every datetime in the codebase goes through here |
| `app/models.py` | All SQLModel tables |
| `app/db.py` | `engine`, `init_db()`, `get_session()` |
| `app/seed.py` | Seeds 9 products/listings against the mock provider |
| `app/crawler/runner.py` | Crawl entrypoint: batches listings (50/batch), exponential backoff, writes CrawlLog |
| `app/crawler/rollup.py` | Aggregates PriceSnapshot → PriceDaily for a given day |
| `app/crawler/providers/base.py` | `AffiliateProvider` Protocol + `RawListing`/`RawPrice` dataclasses |
| `app/crawler/providers/mock.py` | Dev provider — deterministic seeded prices with simulated flash sales |
| `app/crawler/providers/__init__.py` | `get_provider()` factory — reads `AFFILIATE_PROVIDER` from config |

### Adding a real provider (M2)

Implement the `AffiliateProvider` protocol from `providers/base.py` (three methods: `search_products`, `fetch_prices`, `build_affiliate_url`), add it to `get_provider()` in `providers/__init__.py`, and set `AFFILIATE_PROVIDER=shopee` (or `lazada`) in `.env`. See `SPEC.md §0` for the affiliate API access blockers.

## Invariants — never violate

1. **`PriceSnapshot` is append-only.** No UPDATEs, no DELETEs. It's the historical asset that competitors can't copy.
2. **Never hard-delete a `Listing`.** Set `active = False` instead. Deleting breaks historical graphs.
3. **Always use `app.clock.utcnow()`.** Never call `datetime.utcnow()` directly (it's naive; the codebase is tz-aware).
4. **`Clickout` table must be populated from day one.** Without click data, content prioritisation is guesswork.

## Roadmap state (July 2026)

- **M1 done:** Schema, mock provider, crawler runner, daily rollup, seed script.
- **M2 blocked:** `ShopeeProvider` / `LazadaProvider` — waiting on affiliate portal approval and API access (see `SPEC.md §0`).
- **M3 next:** FastAPI web server, Jinja2 templates, Chart.js price graphs, clickout tracking.
- **M4:** LINE OA price-drop alerts (`Alert` table is already in the schema).
