# путь: middleware/session_activity.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from services.auth_service import set_auth_cookie


class SessionActivityMiddleware(BaseHTTPMiddleware):
    """
    Перевыпускает JWT-cookie, если get_current_user положил renew_token в request.state.
    Проверка неактивности 30 мин и редирект на /login — в get_current_user + exception_handler в main.py.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        renew = getattr(request.state, "renew_token", None)
        if renew:
            set_auth_cookie(response, renew)
        return response