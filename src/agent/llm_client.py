import json
import os
from typing import Any

import requests
from requests import RequestException

from src.config import load_env


load_env()

RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_OPENROUTER_MODEL = "qwen/qwen3-next-80b-a3b-instruct:free"
DEFAULT_OLLAMA_MODEL = "llama3.1"


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        self.api_key = api_key or self._api_key_from_env()
        self.model = model or self._model_from_env()
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("LLM_ENABLED", "true").lower() == "true"
        )

    @property
    def available(self) -> bool:
        if self.provider == "ollama":
            return self.enabled
        return bool(self.enabled and self.api_key)

    def complete(self, *, instructions: str, input_text: str) -> str:
        if not self.available:
            return ""
        if self.provider == "ollama":
            return self._complete_ollama(instructions=instructions, input_text=input_text)
        if self.provider == "openrouter":
            return self._complete_openrouter(instructions=instructions, input_text=input_text)
        return self._complete_openai(instructions=instructions, input_text=input_text)

    def _api_key_from_env(self) -> str | None:
        if self.provider == "ollama":
            return None
        if self.provider == "openrouter":
            return os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        return os.getenv("OPENAI_API_KEY")

    def _model_from_env(self) -> str:
        if self.provider == "ollama":
            return os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        if self.provider == "openrouter":
            return (
                os.getenv("OPENROUTER_MODEL")
                or os.getenv("OPENAI_MODEL")
                or DEFAULT_OPENROUTER_MODEL
            )
        return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    def _complete_openai(self, *, instructions: str, input_text: str) -> str:
        try:
            response = requests.post(
                RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": instructions,
                    "input": input_text,
                },
                timeout=30,
            )
            response.raise_for_status()
        except RequestException as exc:
            raise LLMRequestError(str(exc)) from exc
        data = response.json()
        return extract_text(data)

    def _complete_openrouter(self, *, instructions: str, input_text: str) -> str:
        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
                    "X-Title": os.getenv("OPENROUTER_APP_NAME", "NT Motor Maintenance Agent"),
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": input_text},
                    ],
                    "temperature": 0.2,
                },
                timeout=60,
            )
            response.raise_for_status()
        except RequestException as exc:
            raise LLMRequestError(str(exc)) from exc
        data = response.json()
        return extract_chat_completion_text(data)

    def _complete_ollama(self, *, instructions: str, input_text: str) -> str:
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": input_text},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                    },
                },
                timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")),
            )
            response.raise_for_status()
        except RequestException as exc:
            raise LLMRequestError(str(exc)) from exc
        data = response.json()
        return extract_ollama_chat_text(data)

    def complete_json(self, *, instructions: str, input_data: dict[str, Any]) -> dict[str, Any]:
        try:
            text = self.complete(
                instructions=instructions + "\nReturn valid JSON only.",
                input_text=json.dumps(input_data, default=str, indent=2),
            )
        except LLMRequestError as exc:
            return {"llm_error": str(exc)}
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_text = extract_json_object(text)
            if json_text:
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    pass
            return {"raw_text": text}


class LLMRequestError(RuntimeError):
    pass


def extract_text(response: dict[str, Any]) -> str:
    if response.get("output_text"):
        return str(response["output_text"])

    chunks: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                chunks.append(str(content.get("text", "")))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def extract_chat_completion_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", item.get("content", "")))
            for item in content
            if isinstance(item, dict)
        ).strip()
    return str(content).strip()


def extract_ollama_chat_text(response: dict[str, Any]) -> str:
    message = response.get("message", {})
    content = message.get("content", "")
    return str(content).strip()


def extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start : end + 1]
