from app.config import AFFILIATE_PROVIDER, AFFILIATE_TRACKING_ID
from app.crawler.providers.base import AffiliateProvider
from app.crawler.providers.mock import MockProvider


def get_provider() -> AffiliateProvider:
    if AFFILIATE_PROVIDER == "mock":
        return MockProvider()
    if AFFILIATE_PROVIDER == "shopee":
        from app.crawler.providers.shopee import ShopeeProvider
        return ShopeeProvider(tracking_id=AFFILIATE_TRACKING_ID)
    raise NotImplementedError(f"provider '{AFFILIATE_PROVIDER}' ยังไม่ implement")
