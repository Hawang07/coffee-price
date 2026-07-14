from datetime import datetime, timezone


def utcnow() -> datetime:
    """timezone-aware UTC -- ใช้ตัวนี้ทั้งโปรเจกต์ อย่าใช้ datetime.utcnow()"""
    return datetime.now(timezone.utc)
