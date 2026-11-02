import httpx

# ВСТАВЬТЕ ВАШ ТОКЕН СЮДА
API_KEY = "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"
# ВСТАВЬТЕ ID МОДЕЛИ СЮДА
MODEL_ID = "deepseek-ai/DeepSeek-V3-0324"

url = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "model": MODEL_ID,
    "messages": [{"role": "user", "content": "ping"}],
    "max_tokens": 5
}

print("Отправляем запрос...")
try:
    response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
    print(f"Статус код: {response.status_code}")
    print("Ответ сервера:")
    print(response.text)
except Exception as e:
    print(f"Ошибка при выполнении запроса: {e}")