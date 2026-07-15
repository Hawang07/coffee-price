"""Generate Shopee affiliate short links สำหรับทุก listing แล้วอัปเดต DB

วิธีใช้:
  1. ไปที่ affiliate.shopee.co.th → Open API → คัดลอก App ID และ Secret
  2. ใส่ใน .env:
       AFFILIATE_API_KEY=<App ID>
       AFFILIATE_API_SECRET=<Secret>
  3. รัน:
       python -m app.shopee_gen_links
"""
import hashlib
import json
import logging
import time

import httpx
from sqlmodel import select

from app.config import AFFILIATE_API_KEY, AFFILIATE_API_SECRET
from app.db import get_session, init_db
from app.models import Listing, Platform

log = logging.getLogger("shopee_gen_links")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_GRAPHQL_URL = "https://open-api.affiliate.shopee.co.th/graphql"
_DELAY = 0.5


def _sign(app_id: str, secret: str, timestamp: int, payload: str) -> str:
    raw = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _gen_short_link(origin_url: str, app_id: str, secret: str) -> str | None:
    timestamp = int(time.time())
    mutation = (
        'mutation { generateShortLink(input: { originUrl: "'
        + origin_url
        + '", subIds: [""] }) { shortLink } }'
    )
    payload = json.dumps({"query": mutation})
    sig = _sign(app_id, secret, timestamp, payload)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Signature={sig}, Timestamp={timestamp}",
    }
    try:
        r = httpx.post(_GRAPHQL_URL, content=payload, headers=headers, timeout=15)
        if r.status_code != 200:
            log.warning("HTTP %d: %s", r.status_code, r.text[:200])
            return None
        data = r.json()
        short = data.get("data", {}).get("generateShortLink", {}).get("shortLink")
        if not short:
            log.warning("ไม่มี shortLink ใน response: %s", data)
        return short
    except Exception as exc:
        log.warning("request error: %s", exc)
        return None


def run() -> None:
    if not AFFILIATE_API_KEY or not AFFILIATE_API_SECRET:
        print("ERROR: ต้องตั้งค่า AFFILIATE_API_KEY และ AFFILIATE_API_SECRET ใน .env")
        print("       ดูวิธีได้ที่ affiliate.shopee.co.th → Open API")
        return

    init_db()

    with get_session() as s:
        listings = s.exec(
            select(Listing).where(
                Listing.platform == Platform.SHOPEE,
                Listing.active == True,  # noqa: E712
            )
        ).all()

        updated = 0
        for i, lst in enumerate(listings):
            if i > 0:
                time.sleep(_DELAY)

            shopid, itemid = lst.item_id.split("_", 1)
            origin = f"https://shopee.co.th/product/{shopid}/{itemid}"

            short = _gen_short_link(origin, AFFILIATE_API_KEY, AFFILIATE_API_SECRET)
            if not short:
                log.warning("skip listing %d (%s)", lst.id, lst.item_id)
                continue

            lst.affiliate_url = short
            s.add(lst)
            updated += 1
            log.info("✅ listing %d → %s", lst.id, short)

        s.commit()

    print(f"\nอัปเดต affiliate_url {updated}/{len(listings)} listings")


if __name__ == "__main__":
    run()
