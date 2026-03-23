import os
from openai import OpenAI
from .base import LLMClient


class OpenAIClient(LLMClient):

    def __init__(self, model="gpt-4o-mini"):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise Exception("OPENAI_API_KEY environment variable is not set")

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior data engineer, data analyst, analytics engineer, "
                        "and data architect. Produce structured, practical, production-grade "
                        "outputs. Be concise, clear, and implementation-oriented."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3
        )

        content = response.choices[0].message.content

        if not content or content.strip() == "":
            raise Exception("LLM returned empty response")

        return content