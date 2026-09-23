"""
Module: pr_parser.py
Trích xuất thông tin Pull Request và phân giải quan hệ liên kết Issue <-> PR:
- Bóc tách closing keywords trong PR body (fixes #123, closes #456).
- Bóc tách PR metadata (merged_at, additions, deletions, commits).
- Kiểm tra tính hợp lệ của PR giải quyết issue.
"""

import re
from typing import List, Dict, Any, Optional, Set


class PRParser:
    # Regex nhận diện closing keywords theo chuẩn của GitHub
    CLOSING_PATTERN = re.compile(
        r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+(?:https?:\/\/github\.com\/[^\/]+\/[^\/]+\/issues\/)?#?(\d+)",
        re.IGNORECASE
    )

    @classmethod
    def extract_linked_issue_numbers(cls, pr_title: str, pr_body: Optional[str]) -> Set[int]:
        """Trích xuất tất cả issue numbers mà PR này khai báo giải quyết."""
        text = f"{pr_title} {pr_body or ''}"
        matches = cls.CLOSING_PATTERN.findall(text)
        return {int(m) for m in matches if m.isdigit()}

    @classmethod
    def parse_pr_metadata(cls, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Chuẩn hóa dữ liệu PR từ GitHub API response."""
        base_sha = pr_data.get("base", {}).get("sha", "")
        pr_url = pr_data.get("html_url", "")
        base_commit_url = ""
        if base_sha and "/pull/" in pr_url:
            base_commit_url = f"{pr_url.rsplit('/pull/', 1)[0]}/commit/{base_sha}"

        return {
            "pr_number": pr_data.get("number"),
            "pr_title": pr_data.get("title", "").strip(),
            "pr_body": pr_data.get("body", "") or "",
            "pr_url": pr_url,
            "state": pr_data.get("state"),
            "merged": pr_data.get("merged", False) or bool(pr_data.get("merged_at")),
            "merged_at": pr_data.get("merged_at"),
            "created_at": pr_data.get("created_at"),
            "closed_at": pr_data.get("closed_at"),
            "base_branch": pr_data.get("base", {}).get("ref", "main"),
            "head_branch": pr_data.get("head", {}).get("ref", ""),
            "base_commit": base_sha,
            "base_commit_url": base_commit_url,
            "head_commit": pr_data.get("head", {}).get("sha", ""),
            "merge_commit_sha": pr_data.get("merge_commit_sha", ""),
            "author": pr_data.get("user", {}).get("login", ""),
            "is_bot": pr_data.get("user", {}).get("type") == "Bot" or "[bot]" in (pr_data.get("user", {}).get("login", "").lower())
        }
