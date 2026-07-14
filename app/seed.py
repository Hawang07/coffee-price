"""Seed สินค้าตั้งต้น -- รันครั้งเดียว: python -m app.seed"""
import json

from sqlmodel import select

from app.config import expected_commission
from app.crawler.providers import get_provider
from app.db import get_session, init_db
from app.models import Brand, Category, Listing, Platform, Product

# (item_id, brand_slug, brand_name, product_slug, name_th, category, msrp, spec)
SEED = [
    ("mock-timemore-c3", "timemore", "Timemore", "timemore-c3",
     "Timemore Chestnut C3", Category.GRINDER, 2890, {"type": "manual", "burr": "steel 38mm"}),
    ("mock-1zpresso-jx-pro", "1zpresso", "1Zpresso", "1zpresso-jx-pro",
     "1Zpresso JX-Pro", Category.GRINDER, 6500, {"type": "manual", "burr": "steel 48mm"}),
    ("mock-baratza-encore", "baratza", "Baratza", "baratza-encore",
     "Baratza Encore", Category.GRINDER, 8900, {"type": "electric", "burr": "conical 40mm"}),
    ("mock-df64-gen2", "df", "DF", "df64-gen2",
     "DF64 Gen2", Category.GRINDER, 12900, {"type": "electric", "burr": "flat 64mm"}),
    ("mock-eureka-mignon", "eureka", "Eureka", "eureka-mignon-specialita",
     "Eureka Mignon Specialita", Category.GRINDER, 24500, {"type": "electric", "burr": "flat 55mm"}),
    ("mock-breville-bambino", "breville", "Breville", "breville-bambino-plus",
     "Breville Bambino Plus", Category.ESPRESSO_MACHINE, 15900, {"boiler": "thermojet"}),
    ("mock-gaggia-classic", "gaggia", "Gaggia", "gaggia-classic-pro",
     "Gaggia Classic Pro", Category.ESPRESSO_MACHINE, 18500, {"boiler": "single"}),
    ("mock-hario-v60", "hario", "Hario", "hario-v60-02",
     "Hario V60 ดริปเปอร์ 02", Category.DRIP_GEAR, 450, {"material": "ceramic"}),
    ("mock-timemore-scale", "timemore", "Timemore", "timemore-black-mirror",
     "Timemore Black Mirror", Category.SCALE, 2190, {"precision": "0.1g"}),
]


def run() -> None:
    init_db()
    provider = get_provider()

    with get_session() as s:
        for item_id, b_slug, b_name, p_slug, name_th, cat, msrp, spec in SEED:
            brand = s.exec(select(Brand).where(Brand.slug == b_slug)).first()
            if not brand:
                brand = Brand(slug=b_slug, name=b_name)
                s.add(brand)
                s.commit()
                s.refresh(brand)

            product = s.exec(select(Product).where(Product.slug == p_slug)).first()
            if not product:
                product = Product(
                    brand_id=brand.id,
                    slug=p_slug,
                    name_th=name_th,
                    category=cat,
                    msrp=msrp,
                    spec=json.dumps(spec, ensure_ascii=False),
                    expected_commission=expected_commission(msrp),
                )
                s.add(product)
                s.commit()
                s.refresh(product)

            listing = s.exec(select(Listing).where(Listing.item_id == item_id)).first()
            if not listing:
                s.add(Listing(
                    product_id=product.id,
                    platform=Platform.MOCK,
                    item_id=item_id,
                    shop_name="mock shop",
                    affiliate_url=provider.build_affiliate_url(item_id),
                ))
        s.commit()

    print(f"seeded {len(SEED)} products")


if __name__ == "__main__":
    run()
