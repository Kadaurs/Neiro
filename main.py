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


# путь: main.py (фрагмент)
def seed_data() -> None:
    """Создание базовых пользователей и SystemSettings(id=1)."""
    db = SessionLocal()
    try:
        users_to_create = [
            {"email": "admin@local", "password": "admin123", "role": "admin"},
            {"email": "teamlead@local", "password": "teamlead123", "role": "teamlead"},
            {"email": "employee@local", "password": "employee123", "role": "employee"},
        ]

        for u_data in users_to_create:
            user = db.query(User).filter(User.email == u_data["email"]).first()
            if not user:
                logger.info(f"Пользователь {u_data['email']} не найден. Создаем...")
                user = User(
                    email=u_data["email"],
                    hashed_password=pwd_context.hash(u_data["password"]),
                    role=u_data["role"],
                )
                db.add(user)
                db.commit()
                logger.info("=" * 60)
                logger.info(f"Создан пользователь: {u_data['email']} / {u_data['password']}")
                logger.info("=" * 60)
            else:
                # Восстанавливаем роль, если она была изменена
                if user.role != u_data["role"]:
                    user.role = u_data["role"]
                    db.commit()
                    logger.info(f"Роль {u_data['email']} восстановлена на '{u_data['role']}'")

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


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Глобальный обработчик 404: если чат не найден, редирект на главную."""
    if request.headers.get("HX-Request"):
        # Если это HTMX-запрос (например, polling), возвращаем пустоту
        return HTMLResponse("", status_code=404, headers={"HX-Redirect": "/"})

    # Если обычный GET-запрос — редиректим на главную
    return RedirectResponse(url="/", status_code=303)