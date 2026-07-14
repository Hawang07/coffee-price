import logging
import time
from app.clock import utcnow

from sqlmodel import select

from app.config import BASE_URL, CRAWL_BACKOFF_BASE, CRAWL_MAX_RETRY, LISTING_FAIL_THRESHOLD
from app.crawler.providers import get_provider
from app.crawler.rollup import rollup_today
from app.db import get_session, init_db
from app.models import Alert, CrawlLog, Listing, Product, PriceSnapshot

log = logging.getLogger("crawler")
BATCH = 50


def _fetch_with_backoff(provider, item_ids: list[str]):
    for attempt in range(CRAWL_MAX_RETRY):
        try:
            return provider.fetch_prices(item_ids)
        except Exception as exc:  # noqa: BLE001
            wait = CRAWL_BACKOFF_BASE**attempt
            log.warning("fetch failed (attempt %d): %s -- retry in %ds", attempt + 1, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"fetch failed after {CRAWL_MAX_RETRY} attempts")


def run() -> dict:
    init_db()
    provider = get_provider()
    stats = {"listings": 0, "snapshots": 0, "failed": 0, "deactivated": 0}

    with get_session() as s:
        listings = s.exec(select(Listing).where(Listing.active == True)).all()  # noqa: E712
        stats["listings"] = len(listings)
        by_item = {l.item_id: l for l in listings}
        item_ids = list(by_item)

        seen: set[str] = set()
        for i in range(0, len(item_ids), BATCH):
            chunk = item_ids[i : i + BATCH]
            try:
                prices = _fetch_with_backoff(provider, chunk)
            except RuntimeError as exc:
                s.add(CrawlLog(ok=False, message=str(exc)))
                stats["failed"] += len(chunk)
                continue

            for p in prices:
                listing = by_item[p.item_id]
                s.add(
                    PriceSnapshot(
                        listing_id=listing.id,
                        price=p.price,
                        in_stock=p.in_stock,
                        captured_at=utcnow(),
                    )
                )
                listing.last_seen_at = utcnow()
                listing.fail_streak = 0
                s.add(listing)
                seen.add(p.item_id)
                stats["snapshots"] += 1

        # listing ที่ไม่เจอ -> เพิ่ม fail_streak (ห้ามลบ ไม่งั้นกราฟขาด)
        for item_id, listing in by_item.items():
            if item_id in seen:
                continue
            listing.fail_streak += 1
            stats["failed"] += 1
            if listing.fail_streak >= LISTING_FAIL_THRESHOLD:
                listing.active = False
                stats["deactivated"] += 1
                s.add(CrawlLog(listing_id=listing.id, ok=False, message="deactivated: fail streak"))
            s.add(listing)

        s.add(CrawlLog(ok=True, message=str(stats)))
        s.commit()

    rollup_today()
    _fire_alerts()
    return stats


def _fire_alerts() -> None:
    """เช็ก alert ที่ active ทั้งหมด — ถ้าราคาปัจจุบัน ≤ target ให้ push LINE"""
    from app.line_notify import push_price_alert

    with get_session() as s:
        alerts = s.exec(select(Alert).where(Alert.active == True)).all()  # noqa: E712
        if not alerts:
            return

        for alert in alerts:
            listing = s.exec(
                select(Listing).where(
                    Listing.product_id == alert.product_id,
                    Listing.active == True,  # noqa: E712
                ).limit(1)
            ).first()
            if not listing:
                continue

            snap = s.exec(
                select(PriceSnapshot)
                .where(PriceSnapshot.listing_id == listing.id)
                .order_by(PriceSnapshot.captured_at.desc())
                .limit(1)
            ).first()
            if not snap or snap.price > alert.target_price:
                continue

            # หาราคาก่อนหน้า (snapshot ลำดับที่ 2) เพื่อแสดง % ลด
            prev = s.exec(
                select(PriceSnapshot)
                .where(PriceSnapshot.listing_id == listing.id)
                .order_by(PriceSnapshot.captured_at.desc())
                .offset(1)
                .limit(1)
            ).first()
            old_price = prev.price if prev else snap.price

            product = s.get(Product, alert.product_id)
            go_url = f"{BASE_URL}/go/{listing.id}?src=line_alert"

            ok = push_price_alert(
                line_user_id=alert.line_user_id,
                product_name=product.name_th,
                new_price=snap.price,
                old_price=old_price,
                go_url=go_url,
            )
            if ok:
                alert.active = False
                alert.notified_at = utcnow()
                s.add(alert)
                log.info("alert fired: product_id=%d user=%s price=%d",
                         alert.product_id, alert.line_user_id[:8] + "…", snap.price)

        s.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(run())
