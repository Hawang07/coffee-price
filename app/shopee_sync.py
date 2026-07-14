"""อัปเดตราคา Shopee listings โดยใช้ cookie จาก browser

วิธีดู cookie:
  1. เปิด shopee.co.th ใน Chrome แล้ว login
  2. F12 → Application → Cookies → shopee.co.th
  3. copy ค่า SPC_EC และ SPC_F
  4. ใส่ใน .env:
       SHOPEE_SPC_EC=xxxxx
       SHOPEE_SPC_F=xxxxx

ใช้:
    python -m app.shopee_sync
"""
import logging
import os
import time

import httpx
from dotenv import load_dotenv
from sqlmodel import select

from app.clock import utcnow
from app.db import get_session, init_db
from app.models import Listing, Platform, PriceSnapshot

load_dotenv()
log = logging.getLogger("shopee_sync")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_BASE = "https://shopee.co.th"
_DELAY = 1.5


def _thb(raw: int) -> int:
    return max(1, int(raw / 100000))


def fetch_price(shopid: int, itemid: int, client: httpx.Client) -> dict | None:
    url = f"{_BASE}/api/v4/item/get?itemid={itemid}&shopid={shopid}"
    try:
        r = client.get(url, timeout=15)
        if r.status_code != 200:
            log.warning("HTTP %d for %d_%d", r.status_code, shopid, itemid)
            return None
        item = r.json().get("data", {}).get("item")
        if not item:
            return None
        price_raw = item.get("price_min") or item.get("price")
        images = item.get("images") or []
        image_url = f"https://down-th.img.susercontent.com/file/{images[0]}" if images else None
        return {
            "price": _thb(price_raw),
            "in_stock": bool(item.get("stock", 0)) and item.get("status") == 1,
            "name": item.get("name", "")[:60],
            "image_url": image_url,
        }
    except Exception as exc:
        log.warning("fetch error %d_%d: %s", shopid, itemid, exc)
        return None


def run() -> None:
    init_db()

    spc_ec = os.getenv("SHOPEE_SPC_EC", "")
    spc_f = os.getenv("SHOPEE_SPC_F", "")

    if not spc_ec:
        print("ERROR: ต้องตั้งค่า SHOPEE_SPC_EC ใน .env")
        print("       ดูวิธีใน docstring ของไฟล์นี้")
        return

    client = httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": "https://shopee.co.th/",
            "Accept": "application/json",
        },
        cookies={"SPC_EC": spc_ec, "SPC_F": spc_f},
        timeout=15,
        follow_redirects=True,
    )

    with get_session() as s:
        listings = s.exec(
            select(Listing).where(
                Listing.platform == Platform.SHOPEE,
                Listing.active == True,  # noqa: E712
            )
        ).all()

        updated = 0
        for i, listing in enumerate(listings):
            if i > 0:
                time.sleep(_DELAY)

            shopid, itemid = listing.item_id.split("_", 1)
            data = fetch_price(int(shopid), int(itemid), client)
            if not data:
                listing.fail_streak += 1
                s.add(listing)
                log.warning("ดึงราคาไม่ได้: %s (fail_streak=%d)", listing.item_id, listing.fail_streak)
                continue

            s.add(PriceSnapshot(
                listing_id=listing.id,
                price=data["price"],
                in_stock=data["in_stock"],
                captured_at=utcnow(),
            ))
            listing.fail_streak = 0
            listing.last_seen_at = utcnow()
            if data.get("image_url") and not listing.image_url:
                listing.image_url = data["image_url"]
            s.add(listing)
            updated += 1
            log.info("✅ %s → ฿%s in_stock=%s", data["name"], f"{data['price']:,}", data["in_stock"])

        s.commit()

    print(f"\nอัปเดต {updated}/{len(listings)} listings")
    if updated < len(listings):
        print("Tip: ถ้า cookie หมดอายุ ให้ copy ค่าใหม่จาก browser แล้วใส่ใน .env")


if __name__ == "__main__":
    run()
