import hashlib

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlmodel import select

from app.clock import utcnow
from app.db import get_session
from app.models import Clickout, Listing

router = APIRouter()


@router.get("/go/{listing_id}", include_in_schema=False)
def clickout(listing_id: int, request: Request, src: str = "/"):
    with get_session() as s:
        listing = s.get(Listing, listing_id)
        if not listing:
            return RedirectResponse("/", status_code=302)

        ua = request.headers.get("user-agent", "")
        ip = request.client.host if request.client else ""
        ua_hash = hashlib.sha256(f"{ua}{ip}".encode()).hexdigest()[:16]

        s.add(Clickout(
            listing_id=listing_id,
            ts=utcnow(),
            source_page=src[:500],
            referrer=(request.headers.get("referer") or "")[:500] or None,
            ua_hash=ua_hash,
        ))
        s.commit()

    return RedirectResponse(listing.affiliate_url, status_code=302)
