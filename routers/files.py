# путь: routers/files.py
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from models import Chat, ChatUser, User
from services.auth_service import get_current_user
from services.file_service import process_upload

router = APIRouter()


@router.post("/chats/{chat_id}/upload")
async def upload_file(
    chat_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    if not db.get(ChatUser, (chat_id, user.id)) and user.role != "admin":
        raise HTTPException(status_code=403, detail="Нет доступа к чату")

    text = await process_upload(file, chat_id)
    return JSONResponse({
        "ok": True,
        "filename": file.filename,
        "size": len(text),
        "preview": text[:300],
    })