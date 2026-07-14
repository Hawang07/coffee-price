import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.config import CRAWL_ENABLED, CRAWL_HOUR
from app.db import init_db
from app.routes import admin, go, pages

log = logging.getLogger("main")

app = FastAPI(title="Coffee Price Tracker", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(pages.router)
app.include_router(go.router)
app.include_router(admin.router)


@app.on_event("startup")
async def startup():
    init_db()
    if CRAWL_ENABLED:
        _start_scheduler()


def _start_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.crawler.runner import run as crawl_run

        scheduler = BackgroundScheduler(timezone="Asia/Bangkok")
        scheduler.add_job(crawl_run, "cron", hour=CRAWL_HOUR, minute=0)
        scheduler.start()
        log.info("APScheduler started — crawl at %02d:00 ICT", CRAWL_HOUR)
    except Exception as exc:
        log.error("Failed to start scheduler: %s", exc)
