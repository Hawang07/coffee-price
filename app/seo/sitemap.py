from datetime import date

from fastapi import APIRouter
from fastapi.responses import Response
from sqlmodel import select

from app.config import BASE_URL
from app.db import get_session
from app.models import Brand, Product

router = APIRouter()

_BEST_PAGES = [
    ("/best/grinder-10000",         "weekly", "0.8"),
    ("/best/espresso_machine-20000","weekly", "0.7"),
    ("/best/roaster-10000",         "weekly", "0.6"),
    ("/best/drip_gear-2000",        "weekly", "0.6"),
]


def _url(loc: str, changefreq: str = "daily", priority: str = "0.5", lastmod: str = "") -> str:
    lm = f"\n    <lastmod>{lastmod}</lastmod>" if lastmod else ""
    return (
        f"  <url>\n"
        f"    <loc>{loc}</loc>{lm}\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        f"  </url>"
    )


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    today = date.today().isoformat()

    entries = [_url(BASE_URL + "/", "daily", "1.0", today)]

    for path, freq, pri in _BEST_PAGES:
        entries.append(_url(BASE_URL + path, freq, pri, today))

    with get_session() as s:
        products = s.exec(select(Product)).all()
        brands = s.exec(select(Brand)).all()

    for p in products:
        entries.append(_url(f"{BASE_URL}/p/{p.slug}", "daily", "0.9", today))
    for b in brands:
        entries.append(_url(f"{BASE_URL}/brand/{b.slug}", "weekly", "0.5", today))

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>"
    )
    return Response(xml, media_type="application/xml")


@router.get("/robots.txt", include_in_schema=False)
def robots():
    txt = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /go/\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )
    return Response(txt, media_type="text/plain")
