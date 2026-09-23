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

    def build_prompts(self, issue_record: Dict[str, Any], include_base_code: bool = True) -> Tuple[str, str]:
        """Tạo cặp (system_prompt, user_prompt) cho một issue record kèm base_code nếu có."""
        issue = issue_record.get("issue") if isinstance(issue_record.get("issue"), dict) else {}
        repo = issue_record.get("repository") if isinstance(issue_record.get("repository"), dict) else {}

        repo_name = repo.get("full_name") or repo.get("name") or issue_record.get("repo") or "Unknown"
        issue_number = issue.get("number") or issue_record.get("number") or issue_record.get("id", "N/A")
        issue_title = (issue.get("title") or issue_record.get("title") or "").strip()
        issue_body = (issue.get("body") or issue_record.get("body") or "").strip()

        # Cắt bớt body nếu quá dài (> 4000 ký tự) để tránh tràn token
        if len(issue_body) > 4000:
            issue_body = issue_body[:4000] + "\n... [truncated due to length] ..."

        # Trích xuất đoạn code trước khi merge (base_code) để AI so sánh và chấm điểm
        code_context = ""
        if include_base_code:
            base_code_snippets = []
            # Trường hợp base_code lưu trực tiếp trong issue_record
            if issue_record.get("base_code"):
                base_code_snippets.append(f"```\n{issue_record['base_code'].strip()}\n```")
            else:
                files = issue_record.get("changes", {}).get("files", [])
                for f in files:
                    fname = f.get("filename", "")
                    bcode = f.get("base_code", "").strip()
                    if bcode and (f.get("is_source") or f.get("is_test")):
                        base_code_snippets.append(f"File: `{fname}`\n```\n{bcode}\n```")

            if base_code_snippets:
                joined_code = "\n\n".join(base_code_snippets[:3])
                if len(joined_code) > 2500:
                    joined_code = joined_code[:2500] + "\n... [truncated base code] ...\n```"
                code_context = f"\n\nĐoạn code liên quan trước khi sửa/merge (Base Code / Code before merge):\n{joined_code}\n"

        user_prompt = f"""Dưới đây là thông tin về GitHub Issue / Software Requirement cần phân tích:

Repository: {repo_name}
Issue Number: #{issue_number}
Tiêu đề: {issue_title}

Mô tả chi tiết:
{issue_body}{code_context}

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
