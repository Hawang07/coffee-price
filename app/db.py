from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, text

from app.config import DATABASE_URL

Path("./data").mkdir(exist_ok=True)

engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))


def get_session() -> Session:
    return Session(engine)
