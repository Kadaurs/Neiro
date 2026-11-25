# config.py — Настройки приложения.
# Читает переменные из файла .env (секретный ключ, адрес БД, папка Chroma, лимиты файлов,
# время жизни сессии и т.д.) и хранит их в одном объекте settings, доступном из любого места.

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения, читается из .env."""
    SECRET_KEY: str = "dev-secret-change-me"
    DATABASE_URL: str = "sqlite:///./app.db"
    CHROMA_DIR: str = "./chroma_db"

    # JWT / cookie
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    INACTIVITY_MINUTES: int = 30
    COOKIE_NAME: str = "access_token"

    # Файлы
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS: tuple = (".txt", ".log", ".csv", ".json")
    MAX_MESSAGE_LEN: int = 15000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()