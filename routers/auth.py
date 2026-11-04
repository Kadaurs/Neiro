# путь: routers/auth.py
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import User
from services.auth_service import (
    clear_auth_cookie,
    create_access_token,
    set_auth_cookie,
    verify_password,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль"},
            status_code=400,
        )
    user.last_activity_at = datetime.utcnow()
    db.commit()

    token = create_access_token(user.id)
    response = RedirectResponse(url="/", status_code=303)
    set_auth_cookie(response, token)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    clear_auth_cookie(response)
    return response