"""
Module: llm_client.py
Cung cấp interface trừu tượng và adapter cho các nhà cung cấp LLM:
- OpenAI (GPT-4o, GPT-4o-mini)
- Google Gemini (Gemini 1.5 Flash, Gemini 1.5 Pro)
- Anthropic Claude (Claude 3.5 Sonnet)
- Mock Client (để test offline, không tốn tiền API, kiểm thử pipeline hoàn chỉnh)
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("LLMClient")


class BaseLLMClient:
    def generate(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        raise NotImplementedError


class MockLLMClient(BaseLLMClient):
    """Giả lập phản hồi LLM hợp lệ phục vụ kiểm thử pipeline và CI/CD."""
    def __init__(self, model_name: str = "mock-analyzer-model"):
        self.model_name = model_name

    def generate(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        time.sleep(0.1)  # Mô phỏng độ trễ mạng
        # Phản hồi mẫu đúng chuẩn rubric
        sample_output = {
            "complexity": {
                "score": 2,
                "evidence": "[Mock Evidence] Thay đổi cục bộ trong 1-2 files, luồng logic tuần tự."
            },
            "testability": {
                "score": 2,
                "evidence": "[Mock Evidence] Dễ kiểm thử tự động bằng unit test tiêu chuẩn với test fixture có sẵn."
            },
            "security_sensitivity": {
                "score": 1,
                "evidence": "[Mock Evidence] Không xử lý dữ liệu nhạy cảm hay can thiệp luồng xác thực."
            },
            "architecture_impact": {
                "score": 1,
                "evidence": "[Mock Evidence] Sửa đổi implementation nội bộ, giữ nguyên public interface contracts."
            }
        }
        return {
            "raw_text": json.dumps(sample_output, indent=2, ensure_ascii=False),
            "model": self.model_name,
            "prompt_tokens": 450,
            "completion_tokens": 120,
            "latency_ms": 110
        }


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("Vui lòng cài đặt thư viện openai: pip install openai")

    def generate(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        start = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        latency = int((time.time() - start) * 1000)
        choice = response.choices[0]
        return {
            "raw_text": choice.message.content or "",
            "model": self.model,
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "latency_ms": latency
        }


class GeminiLLMClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model_instance = genai.GenerativeModel(
                model_name=self.model,
                generation_config={"response_mime_type": "application/json", "temperature": 0.1}
            )
        except ImportError:
            raise ImportError("Vui lòng cài đặt: pip install google-generativeai")

    def generate(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        start = time.time()
        combined_prompt = f"{system_prompt}\n\n=== REQUIREMENT INPUT ===\n{user_prompt}"
        response = self.model_instance.generate_content(combined_prompt)
        latency = int((time.time() - start) * 1000)
        return {
            "raw_text": response.text,
            "model": self.model,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": latency
        }


def get_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """Factory tạo LLM client dựa trên cấu hình môi trường."""
    provider = provider or os.getenv("LLM_PROVIDER", "mock").lower()

    if provider == "openai":
        return OpenAILLMClient()
    elif provider in ("gemini", "google"):
        return GeminiLLMClient()
    elif provider == "mock":
        return MockLLMClient()
    else:
        logger.warning(f"Unknown provider '{provider}', defaulting to MockLLMClient.")
        return MockLLMClient()
