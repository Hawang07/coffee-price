import secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlmodel import func, select

from app.config import ADMIN_PASS, ADMIN_USER
from app.db import get_session
from app.models import Clickout, Listing, Product

router = APIRouter(prefix="/admin")
security = HTTPBasic()
templates = Jinja2Templates(directory="app/templates")


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

    return templates.TemplateResponse("admin/stats.html", {
        "request": request,
        "rows": rows,
        "days": days,
    })
