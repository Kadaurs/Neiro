# services/file_service.py — Обработка загруженных файлов.
# Проверяет расширение, размер и «сигнатуру» файла, нарезает текст на куски (чанки),
# сохраняет их в векторную БД Chroma (отдельная коллекция для каждого чата)
# и умеет искать похожие куски по запросу (для RAG).
import os
import uuid
from typing import List

import chromadb
from fastapi import HTTPException, UploadFile

from config import settings

_chroma_client = None


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(settings.CHROMA_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
    return _chroma_client


def get_collection(chat_id: int):
    """Коллекция Chroma per-chat."""
    client = get_chroma_client()
    return client.get_or_create_collection(name=f"chat_{chat_id}")


def delete_collection(chat_id: int) -> None:
    client = get_chroma_client()
    try:
        client.delete_collection(name=f"chat_{chat_id}")
    except Exception:
        pass  # коллекции могло не быть


def validate_extension(filename: str) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Недопустимый формат файла. Разрешены только .txt, .log, .csv, .json",
        )


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> List[str]:
    if not text:
        return []
    chunks, start = [], 0
    step = max(1, size - overlap)
    while start < len(text):
        chunks.append(text[start:start + size])
        start += step
    return chunks


async def process_upload(file: UploadFile, chat_id: int) -> str:
    """
    Валидирует файл (расширение, размер, сигнатура: NUL-байты + utf-8),
    чанкует и пишет в Chroma. Возвращает текст файла для превью.
    """
    validate_extension(file.filename or "")

    raw = await file.read()
    if len(raw) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Размер файла превышает допустимый лимит в 5 МБ")
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Файл поврежден, не поддается чтению или пуст")

    head = raw[:4096]
    if b"\x00" in head:
        raise HTTPException(status_code=400, detail="Недопустимый формат файла")
    try:
        head.decode("utf-8")
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Недопустимый формат файла")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Файл поврежден, не поддается чтению или пуст")

    collection = get_collection(chat_id)
    chunks = chunk_text(text)
    if chunks:
        ids = [f"{uuid.uuid4()}" for _ in chunks]
        collection.add(documents=chunks, ids=ids)

    return text


def similarity_search(chat_id: int, query: str, k: int = 3) -> str:
    """Возвращает строку-контекст из Chroma для RAG."""
    try:
        collection = get_collection(chat_id)
        if collection.count() == 0:
            return ""
        result = collection.query(query_texts=[query], n_results=k)
        docs = result.get("documents") or []
        if not docs or not docs[0]:
            return ""
        return "\n---\n".join(docs[0])
    except Exception:
        return ""