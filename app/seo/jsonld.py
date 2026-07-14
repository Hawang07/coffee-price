import json
from typing import Optional


def product_jsonld(
    name: str,
    slug: str,
    base_url: str,
    image: Optional[str],
    offers: list[dict],  # [{"price": int, "url": str, "seller": str}]
) -> str:
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "url": f"{base_url}/p/{slug}",
    }
    if image:
        data["image"] = image

    if offers:
        prices = [o["price"] for o in offers]
        data["offers"] = {
            "@type": "AggregateOffer",
            "priceCurrency": "THB",
            "lowPrice": min(prices),
            "highPrice": max(prices),
            "offerCount": len(offers),
            "offers": [
                {
                    "@type": "Offer",
                    "priceCurrency": "THB",
                    "price": o["price"],
                    "url": o["url"],
                    "seller": {"@type": "Organization", "name": o["seller"]},
                    "availability": "https://schema.org/InStock",
                }
                for o in offers
            ],
        }
    return json.dumps(data, ensure_ascii=False)
