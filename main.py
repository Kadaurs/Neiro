# путь: main.py
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext

from config import settings
from database import Base, SessionLocal, engine
from middleware.session_activity import SessionActivityMiddleware
from models import SystemSettings, User
from routers import auth, chats, files, settings as settings_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("neuro")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_data() -> None:
    """Создание админа и SystemSettings(id=1), если их нет."""
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                email="admin@local",
                hashed_password=pwd_context.hash("admin123"),
                role="admin",
            )
            db.add(admin)
            db.commit()
            logger.info("=" * 60)
            logger.info("Создан администратор по умолчанию: admin@local / admin123")
            logger.info("=" * 60)

        if not db.get(SystemSettings, 1):
            db.add(SystemSettings(id=1, hf_api_url="", hf_api_key="", model_id="", is_active=False))
            db.commit()
            logger.info("Создана запись SystemSettings(id=1) с is_active=False")
    finally:
        db.close()


# create_all вместо Alembic (см. ТЗ)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Neuro MVP1")

app.add_middleware(SessionActivityMiddleware)

# Шаблоны и статика
templates = Jinja2Templates(directory="templates")

# Роутеры
app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(files.router)
app.include_router(settings_router.router)


@app.on_event("startup")
async def on_startup() -> None:
    seed_data()


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    """Любой 401 → редирект на /login (для браузера) или HX-Redirect для HTMX."""
    if request.headers.get("HX-Request"):
        return HTMLResponse("", status_code=401, headers={"HX-Redirect": "/login"})
    return RedirectResponse(url="/login", status_code=303)