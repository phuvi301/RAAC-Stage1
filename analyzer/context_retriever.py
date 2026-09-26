"""
Module: analyzer/context_retriever.py
LLM Context Retriever — Component độc lập, KHÔNG chấm (C,T,S,I).

Nhận vào: issue title, body, repository tree @ base_commit
Trả về: danh sách file paths được chọn (đã validate, không hallucinate, không vượt max_files)

Anti-leakage guarantee:
  - Input CHỈ gồm: issue title, issue body, repository tree @ base_commit
  - KHÔNG truyền vào: PR URL, PR number, PR changed_files, patch, head commit,
    solution commit, PR description, hay bất kỳ thông tin post-fix nào.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ContextRetriever")

# System prompt cho LLM Context Retriever (Section 6 của spec)
_RETRIEVER_SYSTEM_PROMPT = """You are a Repository Context Retriever for software requirement analysis.

Your task is NOT to solve the issue.

Your task is to identify repository files that are most useful for understanding
the requirement described by the GitHub Issue.

Use only:

1. the issue title,
2. the issue body,
3. the repository file tree at the provided pre-fix commit.

Do not infer information from any future solution, pull request, patch,
changed-files list, or post-fix code.

Select files that may help understand:

- the components explicitly mentioned by the issue,
- relevant classes/functions/modules,
- existing tests describing current behavior,
- configuration or dependency files when relevant,
- nearby architectural components when necessary.

Prefer a small, high-signal set of files.

Do not propose a fix.

Return strict JSON only, with this exact format:
{
  "files": [
    {
      "path": "path/to/file.py",
      "reason": "Why this file is relevant to understanding the requirement."
    }
  ]
}"""


def _build_retriever_user_prompt(
    repo: str,
    base_commit: str,
    issue_title: str,
    issue_body: str,
    repository_tree: List[str],
) -> str:
    """
    Tạo user prompt cho LLM Context Retriever.
    KHÔNG chứa bất kỳ thông tin PR, changed_files, head SHA, hay solution nào.
    """
    tree_text = "\n".join(repository_tree)
    # Cắt tree nếu quá dài (> 40000 chars để tránh tràn context)
    if len(tree_text) > 40000:
        tree_text = tree_text[:40000] + "\n... [tree truncated for token budget] ..."

    # Cắt issue body nếu quá dài (> 8000 chars)
    body_text = issue_body
    if len(body_text) > 8000:
        body_text = body_text[:8000] + "\n... [body truncated] ..."

    return f"""Repository:
{repo}

Revision:
{base_commit}

ISSUE

Title:
{issue_title}

Description:
{body_text}

REPOSITORY TREE

{tree_text}"""


def _validate_selected_files(
    raw_files: List[Dict[str, Any]],
    repository_tree: List[str],
    max_files: int,
) -> List[Dict[str, Any]]:
    """
    Validate output của LLM Retriever:
    1. Reject paths không tồn tại trong repository_tree (hallucination)
    2. Remove duplicates
    3. Enforce max_files
    4. Không cho thêm URL hay SHA mới
    """
    tree_set = set(repository_tree)
    seen_paths = set()
    validated = []

    for item in raw_files:
        if not isinstance(item, dict):
            continue
        path = item.get("path", "").strip()
        if not path:
            continue

        # Reject hallucinated paths
        if path not in tree_set:
            logger.warning(f"[ContextRetriever] Rejected hallucinated path: '{path}'")
            continue

        # Remove duplicates
        if path in seen_paths:
            logger.warning(f"[ContextRetriever] Removed duplicate path: '{path}'")
            continue

        seen_paths.add(path)
        validated.append({
            "path": path,
            "reason": str(item.get("reason", ""))[:500]  # cap reason length
        })

        if len(validated) >= max_files:
            break

    return validated


class RepositoryContextRetriever:
    """
    LLM-based file selector cho repo_aware pipeline.

    Tách biệt hoàn toàn với Requirement Analyzer — không chấm C/T/S/I.
    Chỉ chọn file hữu ích để hiểu requirement.
    """

    RETRIEVER_PROMPT_VERSION = "v1"

    def __init__(
        self,
        llm_client,
        max_files: int = 5,
        temperature: float = 0.0,
    ):
        """
        Args:
            llm_client: BaseLLMClient instance (reuse từ llm_client.py)
            max_files: Số file tối đa được chọn (mặc định 5)
            temperature: Temperature khi gọi retriever (mặc định 0.0 để stable)
        """
        self.llm_client = llm_client
        self.max_files = max_files
        self.temperature = temperature

    def retrieve(
        self,
        repo: str,
        base_commit: str,
        issue_title: str,
        issue_body: str,
        repository_tree: List[str],
        issue_id: str = "",
    ) -> Dict[str, Any]:
        """
        Chạy retrieval: gọi LLM với (issue + tree), validate output, trả về kết quả.

        Returns dict:
        {
            "selected_files": [{"path": "...", "reason": "..."}],
            "status": "success" | "empty" | "llm_error" | "parse_error" | "all_rejected",
            "retriever_model": "...",
            "retriever_prompt_version": "v1",
            "raw_llm_output": "...",
            "error": "..." (chỉ khi lỗi)
        }
        """
        if not repository_tree:
            logger.warning(f"[ContextRetriever] Empty repository tree for {issue_id or repo}@{base_commit[:8]}")
            return {
                "selected_files": [],
                "status": "empty",
                "retriever_model": "unknown",
                "retriever_prompt_version": self.RETRIEVER_PROMPT_VERSION,
                "raw_llm_output": "",
                "error": "Empty repository tree"
            }

        system_prompt = _RETRIEVER_SYSTEM_PROMPT
        user_prompt = _build_retriever_user_prompt(
            repo=repo,
            base_commit=base_commit,
            issue_title=issue_title,
            issue_body=issue_body,
            repository_tree=repository_tree,
        )

        logger.info(
            f"[ContextRetriever] Calling LLM for {issue_id or repo}@{base_commit[:8]} "
            f"(tree_size={len(repository_tree)}, max_files={self.max_files})"
        )

        raw_output = ""
        model_name = "unknown"
        try:
            llm_res = self.llm_client.generate(system_prompt, user_prompt, temperature=self.temperature)
            raw_output = llm_res.get("raw_text", "")
            model_name = llm_res.get("model", "unknown")
        except Exception as e:
            logger.error(f"[ContextRetriever] LLM call failed for {issue_id}: {e}")
            return {
                "selected_files": [],
                "status": "llm_error",
                "retriever_model": model_name,
                "retriever_prompt_version": self.RETRIEVER_PROMPT_VERSION,
                "raw_llm_output": raw_output,
                "error": str(e)
            }

        # Parse JSON từ LLM output
        raw_files = []
        try:
            # Thử parse JSON trực tiếp
            parsed = json.loads(raw_output.strip())
            raw_files = parsed.get("files", [])
            if not isinstance(raw_files, list):
                raw_files = []
        except json.JSONDecodeError:
            # Thử tìm JSON block trong output (LLM có thể trả thêm text xung quanh)
            json_match = re.search(r'\{.*?"files"\s*:\s*\[.*?\]\s*\}', raw_output, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    raw_files = parsed.get("files", [])
                    if not isinstance(raw_files, list):
                        raw_files = []
                except Exception:
                    pass

            if not raw_files:
                logger.error(f"[ContextRetriever] Failed to parse LLM JSON for {issue_id}: {raw_output[:200]}")
                return {
                    "selected_files": [],
                    "status": "parse_error",
                    "retriever_model": model_name,
                    "retriever_prompt_version": self.RETRIEVER_PROMPT_VERSION,
                    "raw_llm_output": raw_output,
                    "error": "JSON parse failed"
                }

        # Validate: reject hallucinated paths, deduplicate, enforce max_files
        validated = _validate_selected_files(raw_files, repository_tree, self.max_files)

        if not validated:
            logger.warning(f"[ContextRetriever] No valid files after validation for {issue_id}")
            return {
                "selected_files": [],
                "status": "all_rejected",
                "retriever_model": model_name,
                "retriever_prompt_version": self.RETRIEVER_PROMPT_VERSION,
                "raw_llm_output": raw_output,
                "error": "All proposed paths were rejected (hallucinated or duplicate)"
            }

        logger.info(
            f"[ContextRetriever] Selected {len(validated)}/{len(raw_files)} files for {issue_id or repo}: "
            + ", ".join(f['path'] for f in validated)
        )

        return {
            "selected_files": validated,
            "status": "success",
            "retriever_model": model_name,
            "retriever_prompt_version": self.RETRIEVER_PROMPT_VERSION,
            "raw_llm_output": raw_output,
            "error": None
        }
