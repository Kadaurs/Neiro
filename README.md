# путь: README.md
# Neuro — MVP1

Система совместного анализа логов с LLM. Pure Python (FastAPI + SSR + HTMX).

## Запуск в PyCharm
1. Откройте папку `neuro-mvp1` как проект.
2. Создайте и активируйте виртуальное окружение:
   - Windows: `python -m venv .venv && .venv\Scripts\activate`
   - macOS/Linux: `python -m venv .venv && source .venv/bin/activate`
3. Установите зависимости: `pip install -r requirements.txt`
4. Скопируйте `.env.example` → `.env`, сгенерируйте `SECRET_KEY`:
   `openssl rand -hex 32`
5. Запустите: `uvicorn main:app --reload`
6. Откройте http://127.0.0.1:8000

## Учётные данные по умолчанию

- **admin@local** / **admin123** — создаётся при старте, если БД пуста.

## Чек-лист проверки

1. Вход админом → /settings/api → указать URL, API Key, Model ID → «Проверить подключение».
2. Создать сотрудника и тимлида (через БД/скрипт).
3. Вход сотрудником → личный чат → отправить сообщение → загрузить файл → поиск.
4. Вход тимлидом → создать командный чат → сообщение без `@chatbot` (сохраняется) → с `@chatbot` (ответ LLM).
5. Отозвать ключ админом (is_active=False) → у сотрудника баннер «Сервис недоступен», отправка заблокирована.

## Структура

См. `neuro-mvp1/` — всё в одной папке, без Node.js и Docker.