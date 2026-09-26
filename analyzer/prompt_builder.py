"""
Module: prompt_builder.py
Xây dựng system prompt và user prompt từ dữ liệu issue và template prompt Markdown.

Hỗ trợ hai mode:
  - issue_only  : chỉ dùng issue title + body (behavior gốc)
  - repo_aware  : thêm phần # REPOSITORY CONTEXT (từ ContextBuilder) vào user prompt
"""

import os
import re
import json
from typing import Dict, Any, Tuple, Optional


class PromptBuilder:
    def __init__(self, prompt_version: str = "v3"):
        self.prompt_version = prompt_version
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Đọc nội dung System Prompt từ file markdown tương ứng."""
        filename = f"requirement_analyzer_{self.prompt_version}.md"
        filepath = os.path.join(self.base_dir, "prompts", filename)
        if not os.path.exists(filepath):
            # Fallback sang v2 hoặc v1 nếu không tìm thấy
            filepath = os.path.join(self.base_dir, "prompts", "requirement_analyzer_v2.md")
            if not os.path.exists(filepath):
                filepath = os.path.join(self.base_dir, "prompts", "requirement_analyzer_v1.md")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Trích xuất khối code block ```text trong mục System Prompt
        # Hỗ trợ cả:
        # - v1: '## 1. System Prompt'
        # - v2: '## 1. System Prompt v2.0'
        # - v3: '## 2. System prompt — sao chép nguyên khối'
        match = re.search(r"##\s*\d*\.?\s*System\s+[Pp]rompt[^\n]*\n+```(?:text)?\n(.*?)```", content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Fallback: tìm code block ```text đầu tiên trong file
        fallback_match = re.search(r"```text\n(.*?)```", content, re.DOTALL)
        if fallback_match:
            return fallback_match.group(1).strip()

        return content

    def build_prompts(
        self,
        issue_record: Dict[str, Any],
        include_base_code: Optional[bool] = None,
        repo_context_text: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Tạo cặp (system_prompt, user_prompt) cho một issue record.

        Args:
            issue_record: Dict chứa thông tin issue (title, body, repo, ...).
            include_base_code: (legacy) Đính kèm base_code từ PR files vào prompt.
            repo_context_text: (repo_aware mode) Nội dung phần # REPOSITORY CONTEXT
                               được build bởi ContextBuilder. Nếu None → issue_only mode.
        """
        issue = issue_record.get("issue") if isinstance(issue_record.get("issue"), dict) else {}
        repo = issue_record.get("repository") if isinstance(issue_record.get("repository"), dict) else {}

        repo_name = repo.get("full_name") or repo.get("name") or issue_record.get("repo") or "Unknown"
        issue_number = issue.get("number") or issue_record.get("number") or issue_record.get("id", "N/A")
        issue_title = (issue.get("title") or issue_record.get("title") or "").strip()
        issue_body = (issue.get("body") or issue_record.get("body") or "").strip()

        # Quy cách riêng cho v3 theo đặc tả trong prompts/requirement_analyzer_v3.md (Mục 3)
        if self.prompt_version.lower().startswith("v3"):
            # Đối với v3: đưa body nguyên vẹn (không cắt ngắn), cấu trúc user message dạng JSON chuẩn hóa
            # Không tự ý nối base_code (trừ phi được bật tường minh) để tránh phỏng đoán implementation
            user_payload: Dict[str, Any] = {
                "task": "Phân tích issue theo RAAC Requirement Analyzer v3.0",
                "repo": repo_name,
                "id": str(issue_number),
                "title": issue_title,
                "body": issue_body
            }

            if include_base_code:
                # Nếu người dùng muốn bật base_code cho mục đích thử nghiệm riêng
                base_code_snippets = []
                if issue_record.get("base_code"):
                    base_code_snippets.append(issue_record["base_code"].strip())
                else:
                    files = issue_record.get("changes", {}).get("files", [])
                    for f in files:
                        bcode = f.get("base_code", "").strip()
                        if bcode and (f.get("is_source") or f.get("is_test")):
                            base_code_snippets.append(f"File: {f.get('filename', '')}\n{bcode}")
                if base_code_snippets:
                    user_payload["base_code"] = "\n\n".join(base_code_snippets[:3])

            user_prompt = json.dumps(user_payload, ensure_ascii=False, indent=2)

            # repo_aware mode: nối phần REPOSITORY CONTEXT vào sau JSON payload
            if repo_context_text:
                user_prompt = user_prompt + "\n\n" + repo_context_text

            return self.system_prompt, user_prompt

        # Đối với v1 và v2: giữ nguyên logic truyền thống
        if include_base_code is None:
            include_base_code = True

        # Cắt bớt body nếu quá dài (> 4000 ký tự) để tránh tràn token cho v1/v2
        if len(issue_body) > 4000:
            issue_body = issue_body[:4000] + "\n... [truncated due to length] ..."

        # Trích xuất đoạn code trước khi merge (base_code) để AI so sánh và chấm điểm
        code_context = ""
        if include_base_code:
            base_code_snippets = []
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
