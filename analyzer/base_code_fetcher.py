"""
Module: analyzer/base_code_fetcher.py
Chịu trách nhiệm tự động gọi GitHub API để tải danh sách file và trích xuất base_code 
(mã nguồn trước khi sửa/merge) cho các issue/PR.
Có cơ chế cache cục bộ tại data/raw/base_code_cache.json để tránh gọi trùng lặp và tiết kiệm API quota.
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("BaseCodeFetcher")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_FILE = os.path.join(BASE_DIR, "data", "raw", "base_code_cache.json")


class GitHubBaseCodeFetcher:
    _cache: Optional[Dict[str, Any]] = None
    _github_client = None

    @classmethod
    def _init_client(cls):
        if cls._github_client is None:
            try:
                from scripts.github_api import GitHubAPIClient
                cls._github_client = GitHubAPIClient()
            except Exception as e:
                logger.warning(f"Could not initialize GitHubAPIClient: {e}")
                cls._github_client = None

    @classmethod
    def _load_cache(cls) -> Dict[str, Any]:
        if cls._cache is None:
            cls._cache = {}
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        cls._cache = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not read base_code cache: {e}")
        return cls._cache

    @classmethod
    def _save_cache(cls):
        if cls._cache is not None:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cls._cache, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Could not save base_code cache: {e}")

    @classmethod
    def parse_repo_and_number(cls, issue_record: Dict[str, Any]) -> tuple[Optional[str], Optional[int]]:
        """Trích xuất tên repo (owner/repo) và số PR/issue từ record."""
        repo_name = (
            issue_record.get("repo")
            or issue_record.get("repository", {}).get("full_name")
            or issue_record.get("repository", {}).get("name")
        )
        url = issue_record.get("url", "")
        issue_id = str(issue_record.get("id", ""))

        number = None
        # 1. Thử từ URL (ví dụ https://github.com/pydata/xarray/pull/3733)
        if url:
            m = re.search(r"github\.com/([^/]+/[^/]+)/(?:pull|issues)/(\d+)", url)
            if m:
                if not repo_name or "/" not in repo_name:
                    repo_name = m.group(1)
                number = int(m.group(2))

        # 2. Thử từ issue_id (ví dụ pydata__xarray-3733 hoặc pallets_flask_4074)
        if not number and issue_id:
            m = re.search(r"[-_](\d+)$", issue_id)
            if m:
                number = int(m.group(1))
            if not repo_name:
                parts = issue_id.split("-")[0].split("__")
                if len(parts) == 2:
                    repo_name = f"{parts[0]}/{parts[1]}"

        # 3. Thử từ trường number
        if not number:
            number = issue_record.get("number") or issue_record.get("issue", {}).get("number")
            if number:
                try:
                    number = int(number)
                except (ValueError, TypeError):
                    number = None

        return repo_name, number

    @classmethod
    def fetch_base_code(cls, issue_record: Dict[str, Any], max_files: int = 3, max_chars_per_file: int = 1500) -> Optional[str]:
        """
        Lấy base_code cho issue_record:
        1. Kiểm tra cache
        2. Nếu chưa có, gọi GitHub API lấy files trong PR
        3. Dùng FileParser trích xuất base_code từ patch
        4. Lưu cache và trả về chuỗi base_code
        """
        repo_name, number = cls.parse_repo_and_number(issue_record)
        if not repo_name or not number:
            logger.warning(f"Could not determine repo and PR number for issue: {issue_record.get('id')}")
            return None

        cache_key = f"{repo_name}#{number}"
        cache = cls._load_cache()

        if cache_key in cache:
            return cache[cache_key].get("base_code")

        cls._init_client()
        if not cls._github_client:
            logger.warning("GitHub API client not available.")
            return None

        endpoint = f"repos/{repo_name}/pulls/{number}/files"
        logger.info(f"Fetching base code from GitHub API: {endpoint}...")
        raw_files = cls._github_client.get(endpoint)

        if not raw_files or not isinstance(raw_files, list):
            # Thử lại nếu là issue có linked PR trong changes
            logger.warning(f"No PR files returned for {repo_name}#{number}.")
            return None

        from scripts.file_parser import FileParser

        base_code_snippets: List[str] = []
        files_metadata: List[Dict[str, Any]] = []

        # Ưu tiên source code files trước, sau đó tới test files
        source_files = [f for f in raw_files if FileParser.is_source_file(f.get("filename", ""))]
        test_files = [f for f in raw_files if FileParser.is_test_file(f.get("filename", ""))]
        candidate_files = (source_files + test_files)[:max_files]

        # Nếu không có source/test file, lấy các file đầu tiên
        if not candidate_files:
            candidate_files = raw_files[:max_files]

        for f in candidate_files:
            fname = f.get("filename", "")
            patch = f.get("patch", "")
            bcode = FileParser.extract_base_code(patch, max_chars=max_chars_per_file)
            if bcode:
                base_code_snippets.append(f"File: `{fname}`\n```\n{bcode}\n```")
                files_metadata.append({
                    "filename": fname,
                    "status": f.get("status", "modified"),
                    "base_code": bcode
                })

        joined_code = "\n\n".join(base_code_snippets) if base_code_snippets else ""

        # Lưu vào cache
        cache[cache_key] = {
            "repo": repo_name,
            "number": number,
            "base_code": joined_code,
            "files": files_metadata
        }
        cls._save_cache()

        logger.info(f"Successfully extracted base code for {cache_key} ({len(base_code_snippets)} files).")
        return joined_code
