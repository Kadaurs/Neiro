# путь: routers/chats.py
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import Chat, ChatUser, Message, SystemSettings, User
from services.auth_service import get_current_user, require_teamlead_or_admin
from services.file_service import delete_collection
from services.llm_service import call_llm

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ---------- helpers ----------

def _user_chats(db: Session, user: User):
    """Возвращает личные и командные чаты пользователя."""
    personal = (
        db.query(Chat)
        .join(ChatUser, ChatUser.chat_id == Chat.id)
        .filter(ChatUser.user_id == user.id, Chat.type == "personal")
        .order_by(Chat.id.desc())
        .all()
    )
    team = (
        db.query(Chat)
        .join(ChatUser, ChatUser.chat_id == Chat.id)
        .filter(ChatUser.user_id == user.id, Chat.type == "team")
        .order_by(Chat.id.desc())
        .all()
    )
    return personal, team


def _get_chat_or_403(db: Session, chat_id: int, user: User) -> Chat:
    chat = db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    membership = db.get(ChatUser, (chat_id, user.id))
    if not membership and user.role != "admin":
        raise HTTPException(status_code=403, detail="Нет доступа к чату")
    return chat


def _service_banner(db: Session) -> dict:
    s = db.get(SystemSettings, 1)
    is_active = bool(s and s.is_active)
    return {
        "is_active": is_active,
        "banner_text": None if is_active else "Сервис генерации ответов временно недоступен, обратитесь к администратору",
    }


# ---------- главная ----------

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    personal, team = _user_chats(db, user)
    return templates.TemplateResponse("index.html", {
        "request": request, "user": user,
        "personal_chats": personal, "team_chats": team,
        **_service_banner(db),
    })


# ---------- создание чатов ----------

@router.post("/chats")
async def create_chat(
        title: str = Form(...),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    chat = Chat(title=title[:50], type="personal", created_by=user.id)
    db.add(chat)
    db.flush()
    db.add(ChatUser(chat_id=chat.id, user_id=user.id))
    db.commit()
    return RedirectResponse(url=f"/chats/{chat.id}", status_code=303)


@router.post("/chats/team")
async def create_team_chat(
        title: str = Form(...),
        member_ids: list[int] = Form(default=[]),
        user: User = Depends(require_teamlead_or_admin),
        db: Session = Depends(get_db),
):
    chat = Chat(title=title[:50], type="team", created_by=user.id)
    db.add(chat)
    db.flush()
    db.add(ChatUser(chat_id=chat.id, user_id=user.id))
    for uid in member_ids:
        if uid != user.id and db.get(User, uid):
            db.add(ChatUser(chat_id=chat.id, user_id=uid))
    db.commit()
    return RedirectResponse(url=f"/chats/{chat.id}", status_code=303)


# ---------- просмотр чата ----------

@router.get("/chats/{chat_id}", response_class=HTMLResponse)
async def chat_view(
        chat_id: int,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    chat = _get_chat_or_403(db, chat_id, user)
    messages = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.id.asc()).all()
    personal, team = _user_chats(db, user)
    return templates.TemplateResponse("chat.html", {
        "request": request, "user": user, "chat": chat, "messages": messages,
        "personal_chats": personal, "team_chats": team,
        **_service_banner(db),
    })


# ---------- отправка сообщения (HTMX) ----------

@router.post("/chats/{chat_id}/messages", response_class=HTMLResponse)
async def send_message(
        chat_id: int,
        request: Request,
        content: str = Form(...),
        file_name: str = Form(None),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    chat = _get_chat_or_403(db, chat_id, user)
    text = (content or "").strip()

    # Разрешаем отправку только файла без текста
    if not text and not file_name:
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    if len(text) > settings.MAX_MESSAGE_LEN:
        raise HTTPException(status_code=400, detail="Превышен лимит символов в сообщении")

    user_msg = Message(chat_id=chat_id, user_id=user.id, role="user", content=text, file_name=file_name)
    db.add(user_msg)
    db.commit()

    should_call_llm = False
    if chat.type == "personal":
        should_call_llm = True
    elif chat.type == "team" and "@chatbot" in text:
        should_call_llm = True

    assistant_msg = None
    if should_call_llm:
        try:
            llm_query = text
            if file_name and not text:
                llm_query = f"Пользователь прикрепил файл {file_name}. Пожалуйста, проанализируй его."

            answer = await call_llm(chat_id, llm_query)
            assistant_msg = Message(chat_id=chat_id, user_id=None, role="assistant", content=answer)
            db.add(assistant_msg)
            db.commit()
        except HTTPException as exc:
            db.refresh(user_msg)
            return templates.TemplateResponse("components/message.html", {
                "request": request, "user": user, "chat": chat, "messages": [user_msg],
                "llm_error": exc.detail,
            })

    db.refresh(user_msg)
    if assistant_msg:
        db.refresh(assistant_msg)

    rendered = templates.TemplateResponse("components/message.html", {
        "request": request, "user": user, "chat": chat,
        "messages": [user_msg, assistant_msg] if assistant_msg else [user_msg],
    })
    rendered.headers["HX-Trigger"] = "message-sent"
    return rendered


# ---------- поиск по истории ----------

@router.get("/chats/{chat_id}/search", response_class=HTMLResponse)
async def search_messages(
        chat_id: int,
        q: str,
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    _get_chat_or_403(db, chat_id, user)
    q = (q or "").strip()
    if not q:
        return HTMLResponse("")
    msgs = (
        db.query(Message)
        .filter(Message.chat_id == chat_id, Message.content.ilike(f"%{q}%"))
        .order_by(Message.id.asc())
        .all()
    )
    if not msgs:
        return HTMLResponse('<div class="text-sm text-red-500 p-2">Ничего не найдено</div>')
    return templates.TemplateResponse("components/message.html", {
        "request": request, "user": user, "chat": db.get(Chat, chat_id),
        "messages": msgs, "search_query": q,
    })


# ---------- удаление чата ----------

@router.delete("/chats/{chat_id}")
async def delete_chat(
        chat_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    chat = db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    is_creator = chat.created_by == user.id
    if not (is_creator or user.role == "admin"):
        raise HTTPException(status_code=403, detail="Только создатель или админ может удалить чат")

    db.query(Message).filter(Message.chat_id == chat_id).delete()
    db.query(ChatUser).filter(ChatUser.chat_id == chat_id).delete()
    db.delete(chat)
    db.commit()
    delete_collection(chat_id)
    return RedirectResponse(url="/", status_code=303)


# ---------- участники ----------

@router.post("/chats/{chat_id}/leave")
async def leave_chat(
        chat_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    chat = db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    if chat.created_by == user.id:
        raise HTTPException(
            status_code=400,
            detail="Чтобы покинуть чат, сначала передайте права создателя другому участнику или удалите чат целиком",
        )
    membership = db.get(ChatUser, (chat_id, user.id))
    if membership:
        db.delete(membership)
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.delete("/chats/{chat_id}/members/{user_id}")
async def remove_member(
        chat_id: int,
        user_id: int,
        current: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    chat = db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    if chat.created_by != current.id:
        raise HTTPException(status_code=403, detail="Только создатель может удалять участников")
    if user_id == current.id:
        raise HTTPException(
            status_code=400,
            detail="Чтобы покинуть чат, сначала передайте права создателя другому участнику или удалите чат целиком",
        )
    membership = db.get(ChatUser, (chat_id, user_id))
    if membership:
        db.delete(membership)
        db.commit()
    return RedirectResponse(url=f"/chats/{chat_id}", status_code=303)