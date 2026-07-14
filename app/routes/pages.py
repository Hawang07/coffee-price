import json
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from app.config import BASE_URL
from app.db import get_session
from app.models import Brand, Category, Listing, PriceDaily, PriceSnapshot, Product
from app.seo.jsonld import product_jsonld
from app.seo.sitemap import router as sitemap_router

router = APIRouter()
router.include_router(sitemap_router)
templates = Jinja2Templates(directory="app/templates")


def _latest_prices(s, product_id: int) -> list[dict]:
    """ราคาล่าสุดของทุก listing ที่ active เรียงจากถูกสุด"""
    listings = s.exec(
        select(Listing).where(Listing.product_id == product_id, Listing.active == True)  # noqa: E712
    ).all()

    result = []
    for lst in listings:
        snap = s.exec(
            select(PriceSnapshot)
            .where(PriceSnapshot.listing_id == lst.id)
            .order_by(PriceSnapshot.captured_at.desc())
            .limit(1)
        ).first()
        if snap:
            result.append({
                "listing_id": lst.id,
                "platform": lst.platform.value,
                "shop_name": lst.shop_name or lst.platform.value,
                "price": snap.price,
                "in_stock": snap.in_stock,
                "affiliate_url": lst.affiliate_url,
                "image_url": lst.image_url,
            })
    result.sort(key=lambda x: x["price"])
    return result


def _chart_data(s, listing_ids: list[int], days: int = 90) -> dict:
    """ข้อมูล PriceDaily สำหรับ Chart.js — {listing_id: [(day, min, max), ...]}"""
    since = date.today() - timedelta(days=days)
    rows = s.exec(
        select(PriceDaily)
        .where(PriceDaily.listing_id.in_(listing_ids), PriceDaily.day >= since)
        .order_by(PriceDaily.day)
    ).all()

    out: dict = {}
    for r in rows:
        out.setdefault(r.listing_id, []).append({
            "day": r.day.isoformat(),
            "min": r.min_price,
            "max": r.max_price,
        })
    return out


def _verdict(s, listing_ids: list[int], current_min: Optional[int]) -> dict:
    """สรุปอัตโนมัติ: เทียบราคาปัจจุบันกับ 90 วัน"""
    if current_min is None or not listing_ids:
        return {}

    since_90 = date.today() - timedelta(days=90)
    rows = s.exec(
        select(PriceDaily)
        .where(PriceDaily.listing_id.in_(listing_ids), PriceDaily.day >= since_90)
    ).all()

    if not rows:
        return {}

    all_mins = [r.min_price for r in rows]
    avg_90 = sum(all_mins) / len(all_mins)
    hist_low = min(all_mins)
    hist_low_day = min(rows, key=lambda r: r.min_price).day

    pct_vs_avg = round((current_min - avg_90) / avg_90 * 100, 1)
    return {
        "avg_90": int(avg_90),
        "hist_low": hist_low,
        "hist_low_day": hist_low_day.strftime("%-d %b %Y"),
        "pct_vs_avg": pct_vs_avg,
        "is_good": pct_vs_avg < -5,
    }


# ── Home ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    with get_session() as s:
        products = s.exec(
            select(Product).order_by(Product.expected_commission.desc()).limit(12)
        ).all()
        cards = []
        for p in products:
            prices = _latest_prices(s, p.id)
            has_real = any(not pr["affiliate_url"].startswith("https://example.invalid") for pr in prices)
            image_url = next((pr["image_url"] for pr in prices if pr.get("image_url")), None)
            cards.append({
                "product": p,
                "min_price": prices[0]["price"] if prices else None,
                "has_real": has_real,
                "image_url": image_url,
            })
        # เรียง real listings ขึ้นก่อน
        cards.sort(key=lambda c: (not c["has_real"], -(c["product"].expected_commission or 0)))

    return templates.TemplateResponse(request, "home.html", {"cards": cards})


# ── Product ───────────────────────────────────────────────────────────────────

@router.get("/p/{slug}", response_class=HTMLResponse)
def product_page(slug: str, request: Request, chart_days: int = 90):
    with get_session() as s:
        product = s.exec(select(Product).where(Product.slug == slug)).first()
        if not product:
            raise HTTPException(404)

        brand = s.get(Brand, product.brand_id)
        prices = _latest_prices(s, product.id)
        listing_ids = [p["listing_id"] for p in prices]
        chart = _chart_data(s, listing_ids, chart_days)
        current_min = prices[0]["price"] if prices else None
        verdict = _verdict(s, listing_ids, current_min)

        spec = json.loads(product.spec) if product.spec else {}

        # รูปสินค้าจาก listing ที่ถูกสุด (หรือ listing แรกที่มีรูป)
        product_image = next((p["image_url"] for p in prices if p.get("image_url")), None)

        jsonld = product_jsonld(
            name=product.name_th,
            slug=product.slug,
            base_url=BASE_URL,
            image=product_image,
            offers=[
                {"price": p["price"], "url": p["affiliate_url"], "seller": p["shop_name"]}
                for p in prices if p["in_stock"]
            ],
        )

        # หน้า compare ที่เกี่ยวข้อง (same category, ราคาต่างไม่เกิน 40%)
        related_compares = []
        if current_min:
            siblings = s.exec(
                select(Product).where(
                    Product.category == product.category,
                    Product.id != product.id,
                )
            ).all()
            for sib in siblings:
                sib_prices = _latest_prices(s, sib.id)
                if not sib_prices:
                    continue
                sib_min = sib_prices[0]["price"]
                if abs(sib_min - current_min) / current_min <= 0.40:
                    related_compares.append(sib)
            related_compares = related_compares[:5]

    return templates.TemplateResponse(request, "product.html", {
        "product": product,
        "brand": brand,
        "prices": prices,
        "product_image": product_image,
        "chart": json.dumps(chart, ensure_ascii=False),
        "chart_days": chart_days,
        "verdict": verdict,
        "spec": spec,
        "jsonld": jsonld,
        "related_compares": related_compares,
        "base_url": BASE_URL,
    })


# ── Compare ───────────────────────────────────────────────────────────────────

@router.get("/vs/{slugs}", response_class=HTMLResponse)
def compare_page(slugs: str, request: Request):
    parts = slugs.split("-vs-", 1)
    if len(parts) != 2:
        raise HTTPException(400, "URL ต้องอยู่ในรูป /vs/{slug_a}-vs-{slug_b}")

    with get_session() as s:
        pa = s.exec(select(Product).where(Product.slug == parts[0])).first()
        pb = s.exec(select(Product).where(Product.slug == parts[1])).first()
        if not pa or not pb:
            raise HTTPException(404)

        prices_a = _latest_prices(s, pa.id)
        prices_b = _latest_prices(s, pb.id)
        ids_a = [p["listing_id"] for p in prices_a]
        ids_b = [p["listing_id"] for p in prices_b]
        chart_a = _chart_data(s, ids_a)
        chart_b = _chart_data(s, ids_b)
        spec_a = json.loads(pa.spec) if pa.spec else {}
        spec_b = json.loads(pb.spec) if pb.spec else {}

    return templates.TemplateResponse(request, "compare.html", {
        "pa": pa, "pb": pb,
        "prices_a": prices_a, "prices_b": prices_b,
        "chart_a": json.dumps(chart_a, ensure_ascii=False),
        "chart_b": json.dumps(chart_b, ensure_ascii=False),
        "spec_a": spec_a, "spec_b": spec_b,
        "base_url": BASE_URL,
    })


# ── Best-of ───────────────────────────────────────────────────────────────────

_CATEGORY_LABELS = {
    "grinder": "เครื่องบดกาแฟ",
    "espresso_machine": "เครื่องชงเอสเปรสโซ",
    "auto_machine": "เครื่องชงอัตโนมัติ",
    "drip_gear": "อุปกรณ์ดริป",
    "scale": "เครื่องชั่ง",
    "roaster": "เครื่องคั่วกาแฟ",
}


@router.get("/best/{category}-{budget}", response_class=HTMLResponse)
def best_page(category: str, budget: int, request: Request):
    try:
        cat = Category(category)
    except ValueError:
        raise HTTPException(404)

    with get_session() as s:
        products = s.exec(select(Product).where(Product.category == cat)).all()
        cards = []
        for p in products:
            prices = _latest_prices(s, p.id)
            if not prices:
                continue
            min_price = prices[0]["price"]
            if min_price <= budget:
                cards.append({"product": p, "prices": prices, "min_price": min_price})

    cards.sort(key=lambda c: c["product"].expected_commission or 0, reverse=True)

    return templates.TemplateResponse(request, "best.html", {
        "category": cat,
        "category_label": _CATEGORY_LABELS.get(category, category),
        "budget": budget,
        "cards": cards,
        "base_url": BASE_URL,
    })


# ── Brand ─────────────────────────────────────────────────────────────────────

@router.get("/brand/{slug}", response_class=HTMLResponse)
def brand_page(slug: str, request: Request):
    with get_session() as s:
        brand = s.exec(select(Brand).where(Brand.slug == slug)).first()
        if not brand:
            raise HTTPException(404)

        products = s.exec(
            select(Product).where(Product.brand_id == brand.id)
        ).all()

        cards = []
        for p in products:
            prices = _latest_prices(s, p.id)
            cards.append({"product": p, "min_price": prices[0]["price"] if prices else None})

    return templates.TemplateResponse(request, "brand.html", {
        "brand": brand,
        "cards": cards,
        "base_url": BASE_URL,
    })
