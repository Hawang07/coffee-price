from app.config import AFFILIATE_PROVIDER
from app.crawler.providers.base import AffiliateProvider
from app.crawler.providers.mock import MockProvider


def get_provider() -> AffiliateProvider:
    if AFFILIATE_PROVIDER == "mock":
        return MockProvider()
    # TODO(M2): ShopeeProvider / LazadaProvider -- ต้องยืนยัน official API ก่อน
    raise NotImplementedError(
        f"provider '{AFFILIATE_PROVIDER}' ยังไม่ implement -- ดู SPEC.md §0"
    )
