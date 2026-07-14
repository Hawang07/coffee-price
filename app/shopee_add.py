"""เพิ่ม Shopee listing เข้า DB จาก URL — รันครั้งเดียวต่อสินค้า

ใช้:
    python -m app.shopee_add <SHOPEE_URL> <PRODUCT_SLUG> [AFFILIATE_URL] [PRICE]

ตัวอย่าง:
    # ใส่ราคาตรง ๆ (bypass Playwright)
    python -m app.shopee_add \\
        "https://shopee.co.th/...-i.SHOPID.ITEMID" \\
        home-coffee-roaster \\
        "https://s.shopee.co.th/XXXXXXXXX" \\
        6187
"""
import sys

from sqlmodel import select

from app.clock import utcnow
from app.crawler.providers.shopee import ShopeeProvider, item_id_from_url
from app.db import get_session, init_db
from app.models import Listing, Platform, PriceSnapshot, Product


def add(shopee_url: str, product_slug: str, affiliate_url: str = "", price: int = 0) -> None:
    init_db()

    try:
        item_id = item_id_from_url(shopee_url)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    provider = ShopeeProvider()

    if price:
        # bypass Playwright — ใช้ราคาที่ให้มา
        print(f"ใช้ราคาที่กำหนด: {price:,} บาท (ข้าม Playwright)")
        verified_price = price
        in_stock = True
    else:
        print(f"กำลังตรวจสอบสินค้า {item_id} ...")
        prices = provider.fetch_prices([item_id])
        if not prices:
            print("ERROR: ดึงข้อมูลจาก Shopee ไม่ได้")
            print("ใส่ราคาเป็น argument ที่ 4 เพื่อข้าม: python -m app.shopee_add <URL> <SLUG> <AFF_URL> <PRICE>")
            sys.exit(1)
        verified_price = prices[0].price
        in_stock = prices[0].in_stock

    print(f"item_id={item_id} ราคา={verified_price:,} บาท")

    # ถ้าไม่มี affiliate URL ให้ใช้ URL สินค้าธรรมดา
    final_url = affiliate_url.strip() if affiliate_url.strip() else provider.build_affiliate_url(item_id)
    print(f"affiliate_url: {final_url}")

    final_url = affiliate_url.strip() if affiliate_url.strip() else provider.build_affiliate_url(item_id)
    print(f"affiliate_url: {final_url}")

    with get_session() as s:
        product = s.exec(select(Product).where(Product.slug == product_slug)).first()
        if not product:
            print(f"ERROR: ไม่พบ product slug='{product_slug}' ใน DB")
            sys.exit(1)

        existing = s.exec(
            select(Listing).where(
                Listing.platform == Platform.SHOPEE,
                Listing.item_id == item_id,
            )
        ).first()
        if existing:
            print(f"มี listing นี้ใน DB อยู่แล้ว (id={existing.id})")
            if affiliate_url.strip() and existing.affiliate_url != final_url:
                existing.affiliate_url = final_url
                s.add(existing)
                s.commit()
                print("อัปเดต affiliate_url แล้ว")
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
            affiliate_url=final_url,
        )
        s.add(listing)
        s.flush()
        s.refresh(listing)

        # บันทึก PriceSnapshot แรกทันที
        s.add(PriceSnapshot(
            listing_id=listing.id,
            price=verified_price,
            in_stock=in_stock,
            captured_at=utcnow(),
        ))
        s.commit()
        print(f"เพิ่ม listing สำเร็จ → product='{product.name_th}' ราคาเริ่มต้น {verified_price:,} บาท")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    add(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3] if len(sys.argv) > 3 else "",
        int(sys.argv[4]) if len(sys.argv) > 4 else 0,
    )
