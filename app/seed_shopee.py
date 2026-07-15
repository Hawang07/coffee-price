"""เพิ่ม Shopee listing จริงทั้งหมดเข้า DB — รันครั้งเดียวบน VPS

    python -m app.seed_shopee
"""
from app.shopee_add import add

_LISTINGS = [
    # (shopee_url, product_slug, price_thb)
    ("https://shopee.co.th/product/290055500/22532358257",  "timemore-c3",            1590),
    ("https://shopee.co.th/product/123748046/3332072034",  "1zpresso-jx-pro",        5100),
    ("https://shopee.co.th/product/22442467/6119522881",   "baratza-encore",         6900),
    ("https://shopee.co.th/product/95152937/28331877668",  "df64-gen2",              8900),
    ("https://shopee.co.th/product/236596941/21269509958", "eureka-mignon-specialita", 16500),
    ("https://shopee.co.th/product/101862212/1740945084",  "breville-bambino-plus",  13900),
    ("https://shopee.co.th/product/29940170/5839208055",   "gaggia-classic-pro",     21500),
    ("https://shopee.co.th/product/33972294/27755294293",  "hario-v60-02",             350),
    ("https://shopee.co.th/product/269985909/7455341117",  "timemore-black-mirror",   1690),
    ("https://shopee.co.th/product/1618665376/28340638734", "home-coffee-roaster",    6187),
]


if __name__ == "__main__":
    for url, slug, price in _LISTINGS:
        print(f"\n── {slug} ──")
        add(url, slug, "", price)
    print("\nเพิ่มทุก listing เรียบร้อย")
