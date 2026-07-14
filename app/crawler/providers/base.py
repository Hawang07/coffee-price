from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class RawListing:
    item_id: str
    title: str
    shop_name: str
    price: int          # บาท
    in_stock: bool
    url: str


@dataclass
class RawPrice:
    item_id: str
    price: int
    in_stock: bool


@runtime_checkable
class AffiliateProvider(Protocol):
    """สลับ implementation ผ่าน .env ได้โดยไม่แตะโค้ดส่วนอื่น

    mock   -> dev / ยังไม่ได้รับอนุมัติ affiliate
    shopee -> production
    lazada -> production
    """

    name: str

    def search_products(self, keyword: str, limit: int = 20) -> list[RawListing]:
        ...

    def fetch_prices(self, item_ids: list[str]) -> list[RawPrice]:
        ...

    def build_affiliate_url(self, item_id: str) -> str:
        ...
