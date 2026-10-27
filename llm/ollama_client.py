"""Ollama-first offline inference adapter; never uploads data to third parties."""
import os
import requests


class OllamaClient:
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.model_id = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

    def generate(self, prompt: str, max_tokens: int = 1400) -> str:
        response = requests.post(
            self.base_url + "/api/generate",
            json={"model": self.model_id, "prompt": prompt, "stream": False,
                  "options": {"num_predict": max_tokens, "temperature": 0}},
            timeout=(2, 25),
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data.get("response"), str):
            raise ValueError("Ollama did not return a valid text response")
        return data["response"]
