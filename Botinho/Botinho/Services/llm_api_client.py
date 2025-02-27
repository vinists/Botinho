import requests
from Helper.utils import run_async

from config import Settings, get_settings
settings: Settings = get_settings()


async def send_message(chat_id: str, prompt: str) -> str:
    url = f"{settings.llm_api_url}/chat/{chat_id}"
    json = {"prompt": prompt}

    response = await run_async(requests.post, url, json=json)
    return response.json()["response"]


async def create_with_custom_persona(chat_id: str, persona: str):
    url = f"{settings.llm_api_url}/chat/{chat_id}"
    json = {"prompt": persona}

    await run_async(requests.put, url, json=json)


async def clear(chat_id: str):
    url = f"{settings.llm_api_url}/chat/{chat_id}"

    await run_async(requests.delete, url)


async def get_usage(chat_id: str) -> int:
    url = f"{settings.llm_api_url}/chat/{chat_id}"

    response = await run_async(requests.get, url)
    return response.json()["tokens_used"]
