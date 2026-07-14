"""LINE Messaging API helpers — push price-drop alerts"""
import hashlib
import hmac
import logging

import httpx

from app.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET

log = logging.getLogger("line")

_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def verify_signature(body: bytes, x_line_signature: str) -> bool:
    mac = hmac.new(LINE_CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    import base64
    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, x_line_signature)


def push_price_alert(
    line_user_id: str,
    product_name: str,
    new_price: int,
    old_price: int,
    go_url: str,
) -> bool:
    """ส่ง Flex Message แจ้งราคาลด — return True ถ้าส่งสำเร็จ"""
    if not LINE_CHANNEL_ACCESS_TOKEN:
        log.warning("LINE_CHANNEL_ACCESS_TOKEN ไม่ได้ตั้งค่า — ข้าม push")
        return False

    pct = round((old_price - new_price) / old_price * 100)

    flex = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#e67e22",
            "contents": [{
                "type": "text",
                "text": "แจ้งเตือนราคา",
                "color": "#ffffff",
                "weight": "bold",
                "size": "sm",
            }],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": product_name,
                    "weight": "bold",
                    "wrap": True,
                    "size": "md",
                },
                {
                    "type": "text",
                    "text": f"฿{new_price:,}",
                    "color": "#e67e22",
                    "size": "xxl",
                    "weight": "bold",
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"ราคาเดิม ฿{old_price:,}",
                            "color": "#aaaaaa",
                            "decoration": "line-through",
                            "size": "sm",
                            "flex": 1,
                        },
                        {
                            "type": "text",
                            "text": f"ลด {pct}%",
                            "color": "#27ae60",
                            "weight": "bold",
                            "size": "sm",
                            "align": "end",
                        },
                    ],
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [{
                "type": "button",
                "action": {"type": "uri", "label": "ไปซื้อเลย →", "uri": go_url},
                "style": "primary",
                "color": "#e67e22",
            }],
        },
    }

    payload = {
        "to": line_user_id,
        "messages": [{
            "type": "flex",
            "altText": f"ราคา {product_name} ลดเหลือ ฿{new_price:,} แล้ว!",
            "contents": flex,
        }],
    }

    try:
        r = httpx.post(
            _PUSH_URL,
            json=payload,
            headers={"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"},
            timeout=10,
        )
        r.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log.error("LINE push failed: %s", exc)
        return False
