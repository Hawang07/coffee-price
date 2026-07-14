"""LINE Login OAuth + webhook + alert creation"""
import json
import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from app.clock import utcnow
from app.config import (BASE_URL, LINE_CHANNEL_SECRET, LINE_LOGIN_CHANNEL_ID,
                        LINE_LOGIN_CHANNEL_SECRET)
from app.db import get_session
from app.line_notify import verify_signature
from app.models import Alert, Product

router = APIRouter(prefix="/line")
templates = Jinja2Templates(directory="app/templates")
log = logging.getLogger("line")

# state token store: {token: {"product_id": int, "target_price": int, "exp": float}}
_states: dict[str, dict] = {}
_STATE_TTL = 600  # 10 นาที

_LINE_AUTH_URL = "https://access.line.me/oauth2/v2.1/authorize"
_LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
_LINE_PROFILE_URL = "https://api.line.me/v2/profile"
_REDIRECT_URI = f"{BASE_URL}/line/callback"


# ── Alert init — สร้าง state แล้ว redirect ไป LINE Login ────────────────────

@router.get("/login")
def line_login(product_id: int, target_price: int):
    if not LINE_LOGIN_CHANNEL_ID:
        raise HTTPException(503, "LINE Login ยังไม่ได้ตั้งค่า (LINE_LOGIN_CHANNEL_ID)")

    state = secrets.token_urlsafe(32)
    _states[state] = {"product_id": product_id, "target_price": target_price, "exp": time.time() + _STATE_TTL}

    params = urlencode({
        "response_type": "code",
        "client_id": LINE_LOGIN_CHANNEL_ID,
        "redirect_uri": _REDIRECT_URI,
        "state": state,
        "scope": "profile",
    })
    return RedirectResponse(f"{_LINE_AUTH_URL}?{params}", status_code=302)


# ── LINE Login callback ───────────────────────────────────────────────────────

@router.get("/callback")
def line_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse("/?alert=cancelled", status_code=302)

    ctx = _states.pop(state, None)
    if not ctx or ctx["exp"] < time.time():
        raise HTTPException(400, "state token หมดอายุหรือไม่ถูกต้อง")

    # exchange code → access token
    try:
        r = httpx.post(_LINE_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _REDIRECT_URI,
            "client_id": LINE_LOGIN_CHANNEL_ID,
            "client_secret": LINE_LOGIN_CHANNEL_SECRET,
        }, timeout=10)
        r.raise_for_status()
        access_token = r.json()["access_token"]
    except httpx.HTTPError as exc:
        log.error("LINE token exchange failed: %s", exc)
        raise HTTPException(502, "ไม่สามารถติดต่อ LINE ได้")

    # get profile → userId
    try:
        p = httpx.get(_LINE_PROFILE_URL,
                      headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        p.raise_for_status()
        line_user_id = p.json()["userId"]
    except httpx.HTTPError as exc:
        log.error("LINE profile fetch failed: %s", exc)
        raise HTTPException(502, "ไม่สามารถดึงข้อมูล LINE profile ได้")

    product_id = ctx["product_id"]
    target_price = ctx["target_price"]

    with get_session() as s:
        product = s.get(Product, product_id)
        if not product:
            raise HTTPException(404)

        # ปิด alert เก่าของ user + product นี้ก่อนสร้างใหม่
        old_alerts = s.exec(
            select(Alert).where(
                Alert.line_user_id == line_user_id,
                Alert.product_id == product_id,
                Alert.active == True,  # noqa: E712
            )
        ).all()
        for a in old_alerts:
            a.active = False
            s.add(a)

        s.add(Alert(
            line_user_id=line_user_id,
            product_id=product_id,
            target_price=target_price,
        ))
        s.commit()
        slug = product.slug

    return RedirectResponse(f"/p/{slug}?alert=set&price={target_price}", status_code=302)


# ── LINE Webhook ──────────────────────────────────────────────────────────────

@router.post("/webhook")
async def line_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("x-line-signature", "")

    if LINE_CHANNEL_SECRET and not verify_signature(body, sig):
        raise HTTPException(400, "invalid signature")

    events = json.loads(body).get("events", [])
    for event in events:
        etype = event.get("type")
        uid = event.get("source", {}).get("userId", "")
        if etype == "follow":
            log.info("new follower: %s", uid)
            _reply(event.get("replyToken"), f"userId ของคุณ: {uid}")
        elif etype == "message":
            _reply(event.get("replyToken"), f"userId ของคุณ: {uid}")
        elif etype == "unfollow":
            # deactivate all alerts for this user
            uid = event.get("source", {}).get("userId")
            if uid:
                with get_session() as s:
                    alerts = s.exec(
                        select(Alert).where(Alert.line_user_id == uid, Alert.active == True)  # noqa: E712
                    ).all()
                    for a in alerts:
                        a.active = False
                        s.add(a)
                    s.commit()

    return {"status": "ok"}


def _reply(reply_token: str | None, text: str) -> None:
    from app.config import LINE_CHANNEL_ACCESS_TOKEN
    if not reply_token or not LINE_CHANNEL_ACCESS_TOKEN:
        return
    try:
        httpx.post(
            "https://api.line.me/v2/bot/message/reply",
            json={"replyToken": reply_token, "messages": [{"type": "text", "text": text}]},
            headers={"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"},
            timeout=5,
        )
    except Exception:
        pass
