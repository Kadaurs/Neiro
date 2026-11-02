# путь: services/auth_service.py
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (JWTError, ValueError):
        return None


def set_auth_cookie(response, token: str) -> None:
    """Устанавливает HTTP-only cookie с JWT."""
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # в prod: True
        max_age=settings.JWT_EXPIRE_HOURS * 3600,
        path="/",
    )


def clear_auth_cookie(response) -> None:
    response.delete_cookie(settings.COOKIE_NAME, path="/")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Dependency: достаёт пользователя по cookie.
    Sliding expiration: если прошло > INACTIVITY_MINUTES — 401.
    Иначе обновляет last_activity_at и перевыпускает cookie с новым exp.
    """
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")

    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия истекла")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")

    now = datetime.utcnow()
    if user.last_activity_at is not None:
        delta = now - user.last_activity_at
        if delta > timedelta(minutes=settings.INACTIVITY_MINUTES):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Сессия истекла, пожалуйста, войдите в систему снова",
            )

    # sliding expiration
    user.last_activity_at = now
    db.commit()

    # перевыпуск cookie — делаем в middleware, чтобы гарантированно попасть в response
    request.state.user = user
    request.state.renew_token = create_access_token(user.id)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user


def require_teamlead_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("teamlead", "admin"):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user