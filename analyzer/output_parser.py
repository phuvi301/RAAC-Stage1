"""
Module: output_parser.py
Bóc tách và parse an toàn chuỗi JSON từ phản hồi dạng text của LLM:
- Loại bỏ markdown code fence (```json ... ```).
- Sửa lỗi format phổ biến.
- Trả về Python dict hoặc raise exception rõ ràng.
"""

import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("OutputParser")


class OutputParser:
    @classmethod
    def parse_llm_json(cls, raw_text: str) -> Dict[str, Any]:
        """Trích xuất khối JSON từ output text của LLM."""
        text = raw_text.strip()

        # 1. Thử parse trực tiếp
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Tìm khối markdown ```json ... ``` hoặc ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence_match:
            json_str = fence_match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 3. Tìm cặp ngoặc nhọn đầu tiên và cuối cùng { ... }
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = text[start_idx:end_idx + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Không thể trích xuất JSON hợp lệ từ phản hồi LLM: {raw_text[:300]}...")
