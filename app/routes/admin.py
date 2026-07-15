import secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlmodel import func, select

from app.config import ADMIN_PASS, ADMIN_USER
from app.db import get_session
from app.models import Clickout, Listing, Platform, Product
from app.templates_env import templates

router = APIRouter(prefix="/admin")
security = HTTPBasic()


def _auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.username, ADMIN_USER or "admin") and \
         secrets.compare_digest(credentials.password, ADMIN_PASS or "changeme")
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={"WWW-Authenticate": "Basic"})


@router.get("/stats", response_class=HTMLResponse)
def stats(request: Request, days: int = 30, _=Depends(_auth)):
    since = date.today() - timedelta(days=days)
    with get_session() as s:
        rows = s.exec(
            select(
                Clickout.source_page,
                Listing.id.label("listing_id"),
                Product.name_th,
                func.count(Clickout.id).label("clicks"),
            )
            .join(Listing, Clickout.listing_id == Listing.id)
            .join(Product, Listing.product_id == Product.id)
            .where(func.date(Clickout.ts) >= since)
            .group_by(Clickout.source_page, Listing.id, Product.name_th)
            .order_by(func.count(Clickout.id).desc())
        ).all()

    return templates.TemplateResponse(request, "admin/stats.html", {
        "rows": rows,
        "days": days,
    })


@router.get("/images", response_class=HTMLResponse)
def images_get(request: Request, saved: int = 0, _=Depends(_auth)):
    with get_session() as s:
        rows_raw = s.exec(
            select(Listing, Product)
            .join(Product, Listing.product_id == Product.id)
            .where(Listing.active == True)  # noqa: E712
            .order_by(Listing.image_url.is_(None).desc(), Product.name_th)
        ).all()

        listings = [
            {
                "listing_id": lst.id,
                "name_th": prod.name_th,
                "platform": lst.platform.value,
                "url": lst.affiliate_url,
                "image_url": lst.image_url,
            }
            for lst, prod in rows_raw
        ]

    return templates.TemplateResponse(request, "admin/images.html", {
        "listings": listings,
        "saved": saved or None,
    })


@router.post("/images/{listing_id}")
def images_post(listing_id: int, image_url: str = Form(""), _=Depends(_auth)):
    with get_session() as s:
        lst = s.get(Listing, listing_id)
        if not lst:
            raise HTTPException(404)
        lst.image_url = image_url.strip() or None
        s.add(lst)
        s.commit()
    return RedirectResponse(f"/admin/images?saved={listing_id}", status_code=303)
