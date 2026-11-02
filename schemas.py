# путь: schemas.py
"""Pydantic-схемы для валидации форм. Используются в роутерах."""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginForm(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)


class ChatCreateForm(BaseModel):
    title: str = Field(min_length=1, max_length=50)


class TeamChatCreateForm(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    member_ids: list[int] = Field(default_factory=list)


class MessageForm(BaseModel):
    content: str = Field(max_length=15000)


class ApiSettingsForm(BaseModel):
    hf_api_url: str
    hf_api_key: str = Field(min_length=10, max_length=100)
    model_id: str