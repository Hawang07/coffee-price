import hashlib
import random
from datetime import datetime

from app.crawler.providers.base import AffiliateProvider, RawListing, RawPrice

# สินค้าจำลอง -- ราคาอิงตลาดไทยคร่าว ๆ
_CATALOG = {
    "mock-1zpresso-jx-pro": ("1Zpresso JX-Pro เครื่องบดมือหมุน", "Coffee Gear TH", 6500),
    "mock-timemore-c3": ("Timemore Chestnut C3 เครื่องบดมือหมุน", "Timemore Official", 2890),
    "mock-df64-gen2": ("DF64 Gen2 เครื่องบดไฟฟ้า", "Brew Lab", 12900),
    "mock-baratza-encore": ("Baratza Encore เครื่องบดไฟฟ้า", "Coffee Gear TH", 8900),
    "mock-eureka-mignon": ("Eureka Mignon Specialita", "Espresso House", 24500),
    "mock-breville-bambino": ("Breville Bambino Plus", "Breville Official", 15900),
    "mock-gaggia-classic": ("Gaggia Classic Pro", "Espresso House", 18500),
    "mock-hario-v60": ("Hario V60 ดริปเปอร์ 02", "Hario Official", 450),
    "mock-timemore-scale": ("Timemore Black Mirror เครื่องชั่ง", "Timemore Official", 2190),
}


def _seeded_price(item_id: str, base: int) -> tuple[int, bool]:
    """ราคาแกว่ง deterministic ตามวัน -- ให้กราฟดูสมจริง

    ~8% ของวัน จะเป็นช่วงลดราคาแรง (จำลอง 11.11 / flash sale)
    """
    day = datetime.utcnow().strftime("%Y-%m-%d")
    seed = int(hashlib.md5(f"{item_id}{day}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    if rng.random() < 0.08:
        factor = rng.uniform(0.72, 0.85)      # flash sale
    else:
        factor = rng.uniform(0.94, 1.04)      # ปกติ

    in_stock = rng.random() > 0.05
    return int(base * factor), in_stock


class MockProvider:
    name = "mock"

    def search_products(self, keyword: str, limit: int = 20) -> list[RawListing]:
        out = []
        for item_id, (title, shop, base) in _CATALOG.items():
            if keyword.lower() not in title.lower() and keyword != "*":
                continue
            price, in_stock = _seeded_price(item_id, base)
            out.append(
                RawListing(
                    item_id=item_id,
                    title=title,
                    shop_name=shop,
                    price=price,
                    in_stock=in_stock,
                    url=self.build_affiliate_url(item_id),
                )
            )
        return out[:limit]

    def fetch_prices(self, item_ids: list[str]) -> list[RawPrice]:
        out = []
        for item_id in item_ids:
            entry = _CATALOG.get(item_id)
            if not entry:
                continue
            price, in_stock = _seeded_price(item_id, entry[2])
            out.append(RawPrice(item_id=item_id, price=price, in_stock=in_stock))
        return out

    def build_affiliate_url(self, item_id: str) -> str:
        return f"https://example.invalid/mock/{item_id}?aff=demo"


assert isinstance(MockProvider(), AffiliateProvider)
