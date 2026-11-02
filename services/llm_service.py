# путь: services/llm_service.py
import httpx
from fastapi import HTTPException

from config import settings
from database import SessionLocal
from models import SystemSettings
from services.file_service import similarity_search


def get_active_settings() -> SystemSettings:
    db = SessionLocal()
    try:
        s = db.get(SystemSettings, 1)
        if not s:
            raise HTTPException(status_code=503, detail="Сервис генерации ответов временно недоступен")
        return s
    finally:
        db.close()


def check_service_active() -> SystemSettings:
    s = get_active_settings()
    if not s.is_active:
        raise HTTPException(
            status_code=503,
            detail="Сервис генерации ответов временно недоступен, обратитесь к администратору",
        )
    return s


def build_prompt(user_text: str, rag_context: str) -> list[dict]:
    system_prompt = (
        "Ты — ассистент по анализу логов. Отвечай по существу, "
        "используй предоставленный контекст, если он релевантен."
    )
    messages = [{"role": "system", "content": system_prompt}]
    if rag_context:
        messages.append({
            "role": "system",
            "content": f"Контекст из загруженных файлов чата:\n{rag_context}",
        })
    messages.append({"role": "user", "content": user_text})
    return messages


async def call_llm(chat_id: int, user_text: str) -> str:
    """
    RAG + запрос к LLM (Hugging Face / OpenAI-compatible).
    Возвращает текст ответа или бросает HTTPException.
    """
    cfg = check_service_active()

    rag_context = similarity_search(chat_id, user_text, k=3)
    payload = {
        "model": cfg.model_id,
        "messages": build_prompt(user_text, rag_context),
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {cfg.hf_api_key}",
        "Content-Type": "application/json",
    }
    url = cfg.hf_api_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Нейросеть не отвечает (таймаут)")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Нейросеть не отвечает (ошибка соединения)")

    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail="Нейросеть не отвечает (ошибка API)")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (KeyError, ValueError, IndexError):
        raise HTTPException(status_code=502, detail="Нейросеть вернула некорректный ответ")


async def test_connection(api_url: str, api_key: str, model_id: str) -> bool:
    """Тестовый запрос для админки (кнопка «Проверить подключение»)."""
    url = api_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        return resp.status_code < 400
    except Exception:
        return False