"""เพิ่ม Product + Brand ใหม่เข้า DB — รันครั้งเดียวต่อสินค้า

ใช้:
    python -m app.add_product
"""
import json

from sqlmodel import select

from app.config import expected_commission
from app.db import get_session, init_db
from app.models import Brand, Category, Product

PRODUCTS = [
    # (brand_slug, brand_name, product_slug, name_th, category, msrp, spec)
    (
        "generic", "Generic",
        "home-coffee-roaster",
        "เครื่องคั่วเมล็ดกาแฟลมร้อนสำหรับบ้าน",
        Category.ROASTER,
        6187,
        {"type": "air_roaster", "capacity": "small"},
    ),
]


def run() -> None:
    init_db()
    with get_session() as s:
        for b_slug, b_name, p_slug, name_th, cat, msrp, spec in PRODUCTS:
            brand = s.exec(select(Brand).where(Brand.slug == b_slug)).first()
            if not brand:
                brand = Brand(slug=b_slug, name=b_name)
                s.add(brand)
                s.commit()
                s.refresh(brand)

            existing = s.exec(select(Product).where(Product.slug == p_slug)).first()
            if existing:
                print(f"มีอยู่แล้ว: {p_slug}")
                continue

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
            print(f"เพิ่ม product: {p_slug} ({name_th}) commission={expected_commission(msrp)} บาท")


if __name__ == "__main__":
    run()
