from starlette.templating import Jinja2Templates

from app.config import GOOGLE_SITE_VERIFICATION

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["google_site_verification"] = GOOGLE_SITE_VERIFICATION
