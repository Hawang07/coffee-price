"""one-shot schema migrations — run ก่อน restart หลัง deploy ใหม่

    python -m app.migrate
"""
import logging
import sqlite3

from app.config import DATABASE_URL

log = logging.getLogger("migrate")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_MIGRATIONS = [
    # (description, SQL)
    ("add listing.image_url",
     "ALTER TABLE listing ADD COLUMN image_url TEXT"),
]


def run() -> None:
    db_path = DATABASE_URL.removeprefix("sqlite:///")
    con = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in con.execute("PRAGMA table_info(listing)").fetchall()}
        for desc, sql in _MIGRATIONS:
            col = sql.split("COLUMN")[1].strip().split()[0]
            if col in existing:
                log.info("skip: %s (already exists)", desc)
                continue
            con.execute(sql)
            con.commit()
            log.info("done: %s", desc)
    finally:
        con.close()


if __name__ == "__main__":
    run()
