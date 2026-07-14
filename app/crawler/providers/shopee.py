"""Shopee Thailand provider — ใช้ Playwright headless browser ดึงราคาจริง

Shopee เรนเดอร์ด้วย JS และตั้ง cookie ผ่าน JS จึงต้องใช้ browser จริง

Setup (รันครั้งเดียวบน VPS):
    pip install playwright playwright-stealth
    playwright install chromium
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

from app.crawler.providers.base import AffiliateProvider, RawListing, RawPrice

log = logging.getLogger("shopee")

_BASE = "https://shopee.co.th"
_DELAY = 2.0      # วินาที ระหว่าง page load
_WAIT_MS = 8000   # รอ JS โหลด


def item_id_from_url(url: str) -> str:
    """แปลง Shopee URL เป็น item_id รูปแบบ '{shopid}_{itemid}'

    รองรับ:
      https://shopee.co.th/TITLE-i.SHOPID.ITEMID
      https://shopee.co.th/product/SHOPID/ITEMID
    """
    m = re.search(r"-i\.(\d+)\.(\d+)", url)
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    m = re.search(r"/product/(\d+)/(\d+)", url)
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    raise ValueError(f"ไม่พบ shopid/itemid ใน URL: {url}")


def _parse(item_id: str) -> tuple[int, int]:
    shopid, itemid = item_id.split("_", 1)
    return int(shopid), int(itemid)


def _thb(raw: int) -> int:
    """Shopee เก็บราคาเป็น int หน่วย 1/100000 บาท"""
    return max(1, int(raw / 100000))


def _make_page(pw, stealth: bool = True):
    """สร้าง Playwright page พร้อม stealth (ป้องกัน bot detection)"""
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(
        locale="th-TH",
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.new_page()

    if stealth:
        try:
            from playwright_stealth import Stealth
            Stealth().apply_stealth_sync(page)
        except Exception:
            pass  # stealth optional

    return browser, page


class ShopeeProvider:
    name = "shopee"

    def __init__(self, tracking_id: str = ""):
        self._tracking_id = tracking_id

    # ── internal ─────────────────────────────────────────────────────────────

    def _fetch_one(self, shopid: int, itemid: int) -> Optional[RawPrice]:
        """โหลด product page แล้วดักจับ JSON จาก item/get API"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.error("ต้อง: pip install playwright && playwright install chromium")
            return None

        url = f"{_BASE}/product/{shopid}/{itemid}"
        item_id = f"{shopid}_{itemid}"
        captured: list[dict] = []

        with sync_playwright() as pw:
            browser, page = _make_page(pw)

            def _on_resp(resp):
                if f"itemid={itemid}" in resp.url and "item/get" in resp.url:
                    try:
                        body = resp.json()
                        item = body.get("data", {}).get("item")
                        if item:
                            captured.append(item)
                    except Exception:
                        pass

            page.on("response", _on_resp)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(_WAIT_MS)
            except Exception as exc:
                log.warning("shopee page %s: %s", item_id, exc)
            finally:
                browser.close()

        if not captured:
            # fallback: ลองดึงราคาจาก DOM
            return self._fetch_from_dom(shopid, itemid)

        item = captured[0]
        price_raw = item.get("price_min") or item.get("price")
        if price_raw is None:
            return None
        in_stock = bool(item.get("stock", 0)) and item.get("status") == 1
        return RawPrice(item_id=item_id, price=_thb(price_raw), in_stock=in_stock)

    def _fetch_from_dom(self, shopid: int, itemid: int) -> Optional[RawPrice]:
        """Fallback: ดึงราคาจาก DOM โดยตรง (กรณี API ไม่ถูกดักจับ)"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        url = f"{_BASE}/product/{shopid}/{itemid}"
        item_id = f"{shopid}_{itemid}"

        with sync_playwright() as pw:
            browser, page = _make_page(pw)
            try:
                page.goto(url, wait_until="networkidle", timeout=35000)
                page.wait_for_timeout(3000)

                # Shopee แสดงราคาในรูปแบบ "฿X,XXX" — ดึงจาก element ที่มี฿
                price_text = page.evaluate("""() => {
                    const els = Array.from(document.querySelectorAll('*'));
                    for (const el of els) {
                        if (el.children.length === 0) {
                            const t = el.textContent.trim();
                            if (t.startsWith('฿') && /^฿[\\d,]+$/.test(t)) return t;
                        }
                    }
                    return null;
                }""")

                if price_text:
                    price = int(price_text.replace("฿", "").replace(",", ""))
                    log.info("shopee DOM %s → %d บาท", item_id, price)
                    return RawPrice(item_id=item_id, price=price, in_stock=True)

            except Exception as exc:
                log.warning("shopee DOM %s: %s", item_id, exc)
            finally:
                browser.close()

        return None

    # ── AffiliateProvider protocol ───────────────────────────────────────────

    def fetch_prices(self, item_ids: list[str]) -> list[RawPrice]:
        results = []
        for i, item_id in enumerate(item_ids):
            if i > 0:
                time.sleep(_DELAY)
            try:
                shopid, itemid = _parse(item_id)
            except ValueError:
                log.warning("shopee: item_id รูปแบบผิด: %s", item_id)
                continue

            rp = self._fetch_one(shopid, itemid)
            if rp:
                results.append(rp)
                log.info("shopee: %s → %d บาท in_stock=%s", item_id, rp.price, rp.in_stock)
            else:
                log.warning("shopee: ดึงราคา %s ไม่ได้", item_id)

        return results

    def search_products(self, keyword: str, limit: int = 20) -> list[RawListing]:
        """ค้นหาสินค้าบน Shopee — ใช้สำหรับหา item_id ใหม่ ไม่ใช่ crawl รายวัน"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return []

        search_url = f"{_BASE}/search?keyword={keyword}"
        found: list[dict] = []

        with sync_playwright() as pw:
            browser, page = _make_page(pw)

            def _on_resp(resp):
                if "search_items" in resp.url and resp.status == 200:
                    try:
                        body = resp.json()
                        for entry in (body.get("items") or []):
                            info = entry.get("item_basic", {})
                            if info.get("shopid") and info.get("itemid"):
                                found.append(info)
                    except Exception:
                        pass

            page.on("response", _on_resp)
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
                page.evaluate("window.scrollTo(0, 800)")
                page.wait_for_timeout(8000)
            except Exception as exc:
                log.warning("shopee search '%s': %s", keyword, exc)
            finally:
                browser.close()

        results = []
        for info in found[:limit]:
            iid = f"{info['shopid']}_{info['itemid']}"
            price_raw = info.get("price_min") or info.get("price")
            if price_raw is None:
                continue
            results.append(RawListing(
                item_id=iid,
                title=info.get("name", ""),
                shop_name=info.get("shop_name", ""),
                price=_thb(price_raw),
                in_stock=bool(info.get("stock", 0)),
                url=self.build_affiliate_url(iid),
            ))
        return results

    def build_affiliate_url(self, item_id: str) -> str:
        shopid, itemid = _parse(item_id)
        url = f"{_BASE}/product/{shopid}/{itemid}"
        if self._tracking_id:
            url += f"?af_id={self._tracking_id}"
        return url


assert isinstance(ShopeeProvider(), AffiliateProvider)
