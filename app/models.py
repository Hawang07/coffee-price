from datetime import date, datetime

from app.clock import utcnow
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class Category(str, Enum):
    GRINDER = "grinder"                # ตัวทำเงินหลัก (4,000-10,000 บาท)
    ESPRESSO_MACHINE = "espresso_machine"
    AUTO_MACHINE = "auto_machine"
    DRIP_GEAR = "drip_gear"
    SCALE = "scale"
    ROASTER = "roaster"                # เครื่องคั่วกาแฟ


class Platform(str, Enum):
    SHOPEE = "shopee"
    LAZADA = "lazada"
    MOCK = "mock"


class Brand(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    brand_id: int = Field(foreign_key="brand.id", index=True)
    slug: str = Field(index=True, unique=True)
    name_th: str
    name_en: Optional[str] = None
    category: Category = Field(index=True)
    spec: Optional[str] = None          # JSON string
    msrp: Optional[int] = None          # บาท
    # min(msrp * rate, CAP) -- ใช้จัดลำดับว่าหน้าไหนคุ้มค่าทำก่อน
    expected_commission: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Listing(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("platform", "item_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    platform: Platform
    item_id: str
    shop_name: Optional[str] = None
    affiliate_url: str
    active: bool = Field(default=True, index=True)
    fail_streak: int = Field(default=0)
    last_seen_at: Optional[datetime] = None


class PriceSnapshot(SQLModel, table=True):
    """append-only -- ห้าม UPDATE ห้าม DELETE

    นี่คือสินทรัพย์ที่ทบต้นตามเวลา คู่แข่งหน้าใหม่ลอกไม่ได้
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    captured_at: datetime = Field(default_factory=utcnow, index=True)
    price: int                          # บาท
    in_stock: bool = True


class PriceDaily(SQLModel, table=True):
    """rollup รายวัน สำหรับ query กราฟให้เร็ว"""
    listing_id: int = Field(foreign_key="listing.id", primary_key=True)
    day: date = Field(primary_key=True)
    min_price: int
    max_price: int


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    line_user_id: str = Field(index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    target_price: int
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    notified_at: Optional[datetime] = None


class Clickout(SQLModel, table=True):
    """ถ้าไม่มีตารางนี้ = optimize แบบเดาสุ่มไป 6 เดือน"""
    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    source_page: str = Field(index=True)
    referrer: Optional[str] = None
    ua_hash: Optional[str] = None       # hash เท่านั้น ไม่เก็บ PII ดิบ


class CrawlLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    listing_id: Optional[int] = None
    ok: bool
    message: Optional[str] = None
