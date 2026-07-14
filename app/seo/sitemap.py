from fastapi import APIRouter
from fastapi.responses import Response
from sqlmodel import select

from app.config import BASE_URL
from app.db import get_session
from app.models import Brand, Product

router = APIRouter()


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    urls = [BASE_URL + "/"]

    with get_session() as s:
        products = s.exec(select(Product)).all()
        brands = s.exec(select(Brand)).all()

    for p in products:
        urls.append(f"{BASE_URL}/p/{p.slug}")
    for b in brands:
        urls.append(f"{BASE_URL}/brand/{b.slug}")

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append(f"  <url><loc>{u}</loc></url>")
    lines.append("</urlset>")

    return Response("\n".join(lines), media_type="application/xml")
