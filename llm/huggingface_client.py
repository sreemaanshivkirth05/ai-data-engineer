import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()


class HuggingFaceClient:
    def __init__(self):
        self.model_id = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-7B-Instruct")
        self.api_key = os.getenv("HF_TOKEN")

        if not self.api_key:
            raise ValueError("HF_TOKEN missing in .env")

        self.client = InferenceClient(api_key=self.api_key)

    def generate(self, prompt: str, max_tokens: int = 1400) -> str:
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content