from datetime import date, datetime, timedelta

from sqlmodel import select

from app.db import get_session
from app.models import PriceDaily, PriceSnapshot


def rollup_day(day: date) -> int:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)

    with get_session() as s:
        rows = s.exec(
            select(PriceSnapshot).where(
                PriceSnapshot.captured_at >= start,
                PriceSnapshot.captured_at < end,
            )
        ).all()

        agg: dict[int, list[int]] = {}
        for r in rows:
            agg.setdefault(r.listing_id, []).append(r.price)

        for listing_id, prices in agg.items():
            existing = s.get(PriceDaily, (listing_id, day))
            lo, hi = min(prices), max(prices)
            if existing:
                existing.min_price = min(existing.min_price, lo)
                existing.max_price = max(existing.max_price, hi)
                s.add(existing)
            else:
                s.add(PriceDaily(listing_id=listing_id, day=day, min_price=lo, max_price=hi))
        s.commit()
        return len(agg)


def rollup_today() -> int:
    return rollup_day(date.today())
