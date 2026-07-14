"""เพิ่ม Shopee listing เข้า DB จาก URL — รันครั้งเดียวต่อสินค้า

ใช้:
    python -m app.shopee_add <SHOPEE_URL> <PRODUCT_SLUG> [AFFILIATE_URL]

ตัวอย่าง:
    # ไม่มี affiliate link (ใช้ URL สินค้าธรรมดา)
    python -m app.shopee_add \\
        "https://shopee.co.th/Timemore-C3-i.12345.98765" \\
        timemore-c3

    # มี affiliate link จาก Shopee Affiliate Portal
    python -m app.shopee_add \\
        "https://shopee.co.th/Timemore-C3-i.12345.98765" \\
        timemore-c3 \\
        "https://s.shopee.co.th/XXXXXXXXX"
"""
import sys

from sqlmodel import select

from app.crawler.providers.shopee import ShopeeProvider, item_id_from_url
from app.db import get_session, init_db
from app.models import Listing, Platform, Product


def add(shopee_url: str, product_slug: str, affiliate_url: str = "") -> None:
    init_db()

    try:
        item_id = item_id_from_url(shopee_url)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    provider = ShopeeProvider()

    # ดึงราคาจาก Shopee เพื่อตรวจสอบว่า URL ถูกต้อง
    print(f"กำลังตรวจสอบสินค้า {item_id} ...")
    prices = provider.fetch_prices([item_id])
    if not prices:
        print("ERROR: ดึงข้อมูลจาก Shopee ไม่ได้ — ตรวจสอบ URL อีกครั้ง")
        sys.exit(1)

    p = prices[0]
    print(f"พบสินค้า: item_id={item_id} ราคา={p.price:,} บาท in_stock={p.in_stock}")

    # ถ้าไม่มี affiliate URL ให้ใช้ URL สินค้าธรรมดา
    final_url = affiliate_url.strip() if affiliate_url.strip() else provider.build_affiliate_url(item_id)
    print(f"affiliate_url: {final_url}")

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
            print(f"มี listing นี้ใน DB อยู่แล้ว (id={existing.id})")
            # อัปเดต affiliate_url ถ้ามีของใหม่
            if affiliate_url.strip() and existing.affiliate_url != final_url:
                existing.affiliate_url = final_url
                s.add(existing)
                s.commit()
                print(f"อัปเดต affiliate_url แล้ว")
            if not existing.active:
                existing.active = True
                s.add(existing)
                s.commit()
                print("เปิดใช้งานใหม่แล้ว (active=True)")
            return

        s.add(Listing(
            product_id=product.id,
            platform=Platform.SHOPEE,
            item_id=item_id,
            affiliate_url=final_url,
        ))
        s.commit()
        print(f"เพิ่ม listing สำเร็จ → product='{product.name_th}'")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    add(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
