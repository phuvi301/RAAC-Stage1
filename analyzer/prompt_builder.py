"""
Module: prompt_builder.py
Xây dựng system prompt và user prompt từ dữ liệu issue và template prompt Markdown.
"""

import os
import re
from typing import Dict, Any, Tuple


class PromptBuilder:
    def __init__(self, prompt_version: str = "v2"):
        self.prompt_version = prompt_version
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Đọc nội dung System Prompt từ file markdown tương ứng."""
        filename = f"requirement_analyzer_{self.prompt_version}.md"
        filepath = os.path.join(self.base_dir, "prompts", filename)
        if not os.path.exists(filepath):
            # Fallback sang v1 nếu v2 chưa tồn tại
            filepath = os.path.join(self.base_dir, "prompts", "requirement_analyzer_v1.md")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Trích xuất khối code block ```text trong mục 1. System Prompt
        match = re.search(r"## 1\. System Prompt[^\n]*\n+```text\n(.*?)```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content

    def build_prompts(self, issue_record: Dict[str, Any]) -> Tuple[str, str]:
        """Tạo cặp (system_prompt, user_prompt) cho một issue record."""
        issue = issue_record.get("issue", {})
        repo = issue_record.get("repository", {})

        repo_name = repo.get("full_name", repo.get("name", "Unknown"))
        issue_number = issue.get("number", "N/A")
        issue_title = issue.get("title", "").strip()
        issue_body = issue.get("body", "").strip()

        # Cắt bớt body nếu quá dài (> 4000 ký tự) để tránh tràn token
        if len(issue_body) > 4000:
            issue_body = issue_body[:4000] + "\n... [truncated due to length] ..."

        user_prompt = f"""Dưới đây là thông tin về GitHub Issue / Software Requirement cần phân tích:

Repository: {repo_name}
Issue Number: #{issue_number}
Tiêu đề: {issue_title}

Mô tả chi tiết:
{issue_body}

Hãy phân tích requirement trên theo rubric và trả về kết quả định dạng JSON chính xác:
{{
  "complexity": {{
    "score": <1-5>,
    "evidence": "<trích dẫn/giải thích ngắn gọn>"
  }},
  "testability": {{
    "score": <1-5>,
    "evidence": "<trích dẫn/giải thích ngắn gọn>"
  }},
  "security_sensitivity": {{
    "score": <1-5>,
    "evidence": "<trích dẫn/giải thích ngắn gọn>"
  }},
  "architecture_impact": {{
    "score": <1-5>,
    "evidence": "<trích dẫn/giải thích ngắn gọn>"
  }}
}}"""
        return self.system_prompt, user_prompt
