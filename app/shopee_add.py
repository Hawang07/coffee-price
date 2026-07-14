"""เพิ่ม Shopee listing เข้า DB จาก URL — รันครั้งเดียวต่อสินค้า

ใช้:
    python -m app.shopee_add <SHOPEE_URL> <PRODUCT_SLUG>

ตัวอย่าง:
    python -m app.shopee_add \\
        "https://shopee.co.th/Timemore-Chestnut-C3-i.12345.98765" \\
        timemore-c3
"""
import sys

from sqlmodel import select

from app.config import AFFILIATE_TRACKING_ID
from app.crawler.providers.shopee import ShopeeProvider, item_id_from_url
from app.db import get_session, init_db
from app.models import Listing, Platform, Product


def add(shopee_url: str, product_slug: str) -> None:
    init_db()

    try:
        item_id = item_id_from_url(shopee_url)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    provider = ShopeeProvider(tracking_id=AFFILIATE_TRACKING_ID)

    # ดึงราคาจาก Shopee API เพื่อตรวจสอบว่า URL ถูกต้อง
    prices = provider.fetch_prices([item_id])
    if not prices:
        print(f"ERROR: ดึงข้อมูลจาก Shopee ไม่ได้ — ตรวจสอบ URL อีกครั้ง")
        sys.exit(1)

    p = prices[0]
    print(f"พบสินค้า: item_id={item_id} ราคา={p.price} บาท in_stock={p.in_stock}")

    with get_session() as s:
        product = s.exec(select(Product).where(Product.slug == product_slug)).first()
        if not product:
            print(f"ERROR: ไม่พบ product slug='{product_slug}' ใน DB")
            print("       รัน 'python -m app.seed' ก่อน หรือตรวจสอบ slug ให้ถูกต้อง")
            sys.exit(1)

        existing = s.exec(
            select(Listing).where(
                Listing.platform == Platform.SHOPEE,
                Listing.item_id == item_id,
            )
        ).first()
        if existing:
            print(f"มี listing นี้ใน DB อยู่แล้ว (id={existing.id}, active={existing.active})")
            if not existing.active:
                existing.active = True
                s.add(existing)
                s.commit()
                print("เปิดใช้งานใหม่แล้ว (active=True)")
            return

        listing = Listing(
            product_id=product.id,
            platform=Platform.SHOPEE,
            item_id=item_id,
            affiliate_url=provider.build_affiliate_url(item_id),
        )
        s.add(listing)
        s.commit()
        print(f"เพิ่ม listing สำเร็จ → product='{product.name_th}' item_id={item_id}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    add(sys.argv[1], sys.argv[2])
