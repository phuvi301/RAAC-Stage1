"""
Module: llm_client.py
Cung cấp interface trừu tượng và adapter cho các nhà cung cấp LLM:
- 9Router (Local AI Gateway tương thích OpenAI: Claude, Gemini, OpenAI, DeepSeek, v.v.)
- OpenAI (GPT-4o, GPT-4o-mini)
- Google Gemini (Gemini 1.5 Flash, Gemini 1.5 Pro)
- Anthropic Claude (Claude 3.5 Sonnet)
- Mock Client (để test offline, không tốn tiền API, kiểm thử pipeline hoàn chỉnh)
"""

import os
import sys
import json
import time
import logging
import sqlite3
from typing import Dict, Any, Optional
from dotenv import load_dotenv

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()
logger = logging.getLogger("LLMClient")


def _detect_local_9router_key() -> Optional[str]:
    """Tự động tìm API key từ cơ sở dữ liệu SQLite của 9Router trên máy nếu có."""
    possible_paths = [
        os.path.expanduser(r"~\AppData\Roaming\9router\db\data.sqlite"),
        os.path.expanduser(r"~/.9router/db/data.sqlite"),
        os.path.expanduser(r"~/.config/9router/db/data.sqlite"),
    ]
    for db_path in possible_paths:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT key FROM apiKeys WHERE isActive = 1 ORDER BY createdAt DESC LIMIT 1")
                row = cursor.fetchone()
                conn.close()
                if row and row[0]:
                    return row[0]
            except Exception:
                pass
    return None


class BaseLLMClient:
    def generate(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        raise NotImplementedError


class MockLLMClient(BaseLLMClient):
    """Giả lập phản hồi LLM hợp lệ phục vụ kiểm thử pipeline và CI/CD."""
    def __init__(self, model_name: str = "mock-analyzer-model"):
        self.model_name = model_name

    def generate(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
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


class NineRouterLLMClient(BaseLLMClient):
    """Client kết nối tới 9Router (AI Gateway / Proxy tương thích chuẩn OpenAI API).
    Hỗ trợ định tuyến thông minh tới Claude, Gemini, GPT, DeepSeek qua cổng local 20128.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
        default_temperature: float = 0.0
    ):
        self.api_key = (
            api_key
            or os.getenv("NINEROUTER_API_KEY")
            or os.getenv("ROUTER9_API_KEY")
            or _detect_local_9router_key()
            or os.getenv("OPENAI_API_KEY")
            or "9router"
        )
        self.base_url = (
            base_url
            or os.getenv("NINEROUTER_BASE_URL")
            or os.getenv("ROUTER9_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "http://127.0.0.1:20128/v1"
        )
        self.model = (
            model
            or os.getenv("NINEROUTER_MODEL")
            or os.getenv("ROUTER9_MODEL")
            or "ag/gemini-3.8-flash"
        )
        self.timeout = timeout
        self.default_temperature = default_temperature
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        except ImportError:
            raise ImportError("Vui lòng cài đặt thư viện openai: pip install openai")

    def generate(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        start = time.time()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        temp = temperature if temperature is not None else self.default_temperature

        # Thử với response_format json_object trước, nếu model phía sau không hỗ trợ thì fallback
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                response_format={"type": "json_object"}
            )
        except Exception as e:
            err_msg = str(e).lower()
            if "response_format" in err_msg or "json_object" in err_msg or "400" in err_msg:
                logger.warning(f"9Router gọi với response_format gặp lỗi ({e}), thử lại không dùng response_format...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp
                )
            else:
                raise e

        latency = int((time.time() - start) * 1000)
        choice = response.choices[0]
        content = choice.message.content or ""

        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return {
            "raw_text": content,
            "model": self.model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency
        }


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None, default_temperature: float = 0.0):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.default_temperature = default_temperature
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            raise ImportError("Vui lòng cài đặt thư viện openai: pip install openai")

    def generate(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        start = time.time()
        temp = temperature if temperature is not None else self.default_temperature
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temp,
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
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, default_temperature: float = 0.0):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.default_temperature = default_temperature
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model_instance = genai.GenerativeModel(
                model_name=self.model
            )
        except ImportError:
            raise ImportError("Vui lòng cài đặt: pip install google-generativeai")

    def generate(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        start = time.time()
        temp = temperature if temperature is not None else self.default_temperature
        combined_prompt = f"{system_prompt}\n\n=== REQUIREMENT INPUT ===\n{user_prompt}"
        response = self.model_instance.generate_content(
            combined_prompt,
            generation_config={"response_mime_type": "application/json", "temperature": temp}
        )
        latency = int((time.time() - start) * 1000)
        return {
            "raw_text": response.text,
            "model": self.model,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": latency
        }


class AnthropicLLMClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, default_temperature: float = 0.0):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.default_temperature = default_temperature
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("Vui lòng cài đặt: pip install anthropic")

    def generate(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        start = time.time()
        temp = temperature if temperature is not None else self.default_temperature
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temp,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        latency = int((time.time() - start) * 1000)
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
        return {
            "raw_text": content,
            "model": self.model,
            "prompt_tokens": response.usage.input_tokens if response.usage else 0,
            "completion_tokens": response.usage.output_tokens if response.usage else 0,
            "latency_ms": latency
        }


def get_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """Factory tạo LLM client dựa trên cấu hình môi trường."""
    provider = provider or os.getenv("LLM_PROVIDER", "mock").lower()

    if provider in ("9router", "ninerouter", "router9"):
        return NineRouterLLMClient()
    elif provider == "openai":
        return OpenAILLMClient()
    elif provider in ("gemini", "google"):
        return GeminiLLMClient()
    elif provider in ("anthropic", "claude"):
        return AnthropicLLMClient()
    elif provider == "mock":
        return MockLLMClient()
    else:
        logger.warning(f"Unknown provider '{provider}', defaulting to MockLLMClient.")
        return MockLLMClient()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Kiểm tra kết nối tới LLM Client (9Router, OpenAI, Gemini, Anthropic, Mock)")
    parser.add_argument("--provider", default="9router", help="Provider: 9router | openai | gemini | anthropic | mock")
    parser.add_argument("--model", default=None, help="Tùy chọn ghi đè model ID")
    parser.add_argument("--base-url", default=None, help="Tùy chọn ghi đè base URL")
    args = parser.parse_args()

    print(f"=== Kiểm tra kết nối tới LLM Provider: {args.provider} ===")
    client = get_llm_client(args.provider)
    if args.model and hasattr(client, "model"):
        client.model = args.model
    if args.base_url and hasattr(client, "base_url"):
        client.base_url = args.base_url

    if hasattr(client, "base_url"):
        print(f"Base URL: {client.base_url}")
    if hasattr(client, "model"):
        print(f"Target Model: {client.model}")

    test_sys = "Bạn là trợ lý AI đánh giá yêu cầu phần mềm. Luôn trả về phản hồi theo định dạng JSON hợp lệ."
    test_user = "Hãy trả về một JSON mẫu có key 'status' mang giá trị 'ok' và 'message' mang giá trị 'Connection to 9Router verified!'."

    try:
        result = client.generate(test_sys, test_user)
        print("\n Kết nối thành công!")
        print(f"- Model phản hồi: {result.get('model')}")
        print(f"- Độ trễ (Latency): {result.get('latency_ms')} ms")
        print(f"- Tokens: prompt={result.get('prompt_tokens')}, completion={result.get('completion_tokens')}")
        print(f"- Nội dung raw_text:\n{result.get('raw_text')}")
    except Exception as ex:
        print(f"\n Kết nối thất bại: {ex}")
