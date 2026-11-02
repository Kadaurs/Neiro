# путь: routers/settings.py
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import SystemSettings, User
from services.auth_service import require_admin
from services.llm_service import test_connection

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/settings/api", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    s = db.get(SystemSettings, 1) or SystemSettings(id=1, hf_api_url="", hf_api_key="", model_id="", is_active=False)
    return templates.TemplateResponse("settings.html", {
        "request": request, "user": user, "settings": s, "message": None, "error": None,
    })


def _validate(url: str, key: str, model_id: str) -> str | None:
    if not url.startswith("https://"):
        return "URL должен начинаться с https://"
    if not (10 <= len(key) <= 100):
        return "API Key должен быть от 10 до 100 символов"
    if not model_id or " " in model_id:
        return "Model ID не должен содержать пробелов"
    return None


@router.post("/settings/api", response_class=HTMLResponse)
async def save_settings(
    request: Request,
    hf_api_url: str = Form(...),
    hf_api_key: str = Form(...),
    model_id: str = Form(...),
    action: str = Form("save"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    s = db.get(SystemSettings, 1)
    if not s:
        s = SystemSettings(id=1)
        db.add(s)

    error = _validate(hf_api_url, hf_api_key, model_id)
    s.hf_api_url = hf_api_url
    s.hf_api_key = hf_api_key
    s.model_id = model_id

    if error:
        s.is_active = False
        db.commit()
        return templates.TemplateResponse("settings.html", {
            "request": request, "user": user, "settings": s, "message": None, "error": error,
        })

    if action == "test":
        ok = await test_connection(hf_api_url, hf_api_key, model_id)
        s.is_active = ok
        db.commit()
        msg = "Подключение успешно, настройки активны" if ok else "API ключ не прошел валидацию"
        return templates.TemplateResponse("settings.html", {
            "request": request, "user": user, "settings": s,
            "message": msg if ok else None, "error": None if ok else msg,
        })

    # простое сохранение без теста — считаем валидным по формату, но не активным
    s.is_active = False
    db.commit()
    return RedirectResponse(url="/settings/api", status_code=303)