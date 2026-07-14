import os
from dotenv import load_dotenv

load_dotenv()


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# affiliate
AFFILIATE_PROVIDER = os.getenv("AFFILIATE_PROVIDER", "mock")  # mock | shopee | lazada
AFFILIATE_API_KEY = os.getenv("AFFILIATE_API_KEY", "")
AFFILIATE_API_SECRET = os.getenv("AFFILIATE_API_SECRET", "")
AFFILIATE_TRACKING_ID = os.getenv("AFFILIATE_TRACKING_ID", "")

# เพดานค่าคอมมิชชั่นต่อ 1 คำสั่งซื้อ (บาท)
# Shopee TH = 225 (ณ เม.ย. 2569) -- ยืนยันใน portal ก่อน production
COMMISSION_CAP = _int("COMMISSION_CAP", 225)
# อัตราคอมมิชชั่นโดยประมาณ (ยืนยันหมวดเครื่องใช้ไฟฟ้าใน portal)
COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", "0.03"))

# crawler
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "changeme")

CRAWL_ENABLED = os.getenv("CRAWL_ENABLED", "true").lower() == "true"
CRAWL_HOUR = _int("CRAWL_HOUR", 3)
CRAWL_MAX_RETRY = _int("CRAWL_MAX_RETRY", 5)
CRAWL_BACKOFF_BASE = _int("CRAWL_BACKOFF_BASE", 2)
# fail ติดกันกี่วัน ถึงปิด listing
LISTING_FAIL_THRESHOLD = _int("LISTING_FAIL_THRESHOLD", 7)


def expected_commission(price: int) -> int:
    """คอมฯ ที่คาดว่าจะได้ = min(price * rate, CAP)

    เพดานเริ่มกัดที่ CAP / RATE  (225 / 0.03 = 7,500 บาท)
    สินค้าแพงกว่านั้นไม่ได้เงินเพิ่ม -> ใช้ค่านี้จัดลำดับความสำคัญของหน้า
    """
    return min(int(price * COMMISSION_RATE), COMMISSION_CAP)
