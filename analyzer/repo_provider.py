"""
Module: analyzer/repo_provider.py
Chịu trách nhiệm lấy repository tree và file contents từ GitHub API tại một commit cụ thể (base_commit).

Quan trọng — Anti-leakage:
  - Mọi thứ được fetch đúng tại `base_commit`, KHÔNG từ HEAD/main/master.
  - Không sử dụng thông tin PR, changed_files, patch hay solution commit.

Caching:
  - Tree cache: (repo, base_commit) → data/raw/repo_tree_cache/{repo_slug}_{commit8}.json
  - File cache: (repo, base_commit, path) → data/raw/file_content_cache/{repo_slug}_{commit8}/{path_hash}.json
"""

import os
import re
import json
import base64
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("RepoProvider")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TREE_CACHE_DIR = os.path.join(BASE_DIR, "data", "raw", "repo_tree_cache")
FILE_CACHE_DIR = os.path.join(BASE_DIR, "data", "raw", "file_content_cache")

# Extensions / patterns bị loại khỏi tree (binary, build artifacts, junk)
_EXCLUDED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bmp", ".webp",
    ".pdf", ".zip", ".whl", ".tar", ".gz", ".bz2", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".a", ".lib",
    ".pyc", ".pyo", ".class", ".o",
    ".db", ".sqlite", ".sqlite3",
    ".lock",  # pipfile.lock / package-lock.json thường rất lớn và ít hữu ích
}

_EXCLUDED_PREFIXES = (
    ".git/", "node_modules/", "dist/", "build/", "coverage/",
    "__pycache__/", ".tox/", ".eggs/", "*.egg-info/", ".mypy_cache/",
    ".pytest_cache/", "htmlcov/", "site-packages/",
)

# Tối đa số paths trả về trong tree (để tránh gửi quá nhiều token cho LLM)
MAX_TREE_PATHS = 600


def _slug(repo: str) -> str:
    """Chuyển 'owner/repo' thành 'owner__repo' để dùng trong tên file cache."""
    return repo.replace("/", "__")


def _commit8(commit: str) -> str:
    """Lấy 8 ký tự đầu của commit SHA."""
    return commit[:8] if commit else "unknown"


def _is_excluded(path: str) -> bool:
    """Kiểm tra xem path có thuộc danh sách bị loại không."""
    lower_path = path.lower()
    # Kiểm tra prefix
    for prefix in _EXCLUDED_PREFIXES:
        if lower_path.startswith(prefix.replace("*", "")):
            return True
    # Kiểm tra extension
    _, ext = os.path.splitext(lower_path)
    if ext in _EXCLUDED_EXTENSIONS:
        return True
    # Loại bỏ .egg-info và tương tự
    if ".egg-info" in lower_path or "__pycache__" in lower_path:
        return True
    return False


def _path_hash(path: str) -> str:
    """Tạo hash ngắn để dùng làm tên file cache cho một path."""
    return hashlib.md5(path.encode()).hexdigest()[:12]


def _get_github_client():
    """Lấy GitHubAPIClient đã có trong scripts/github_api.py."""
    import sys
    sys.path.insert(0, BASE_DIR)
    from scripts.github_api import GitHubAPIClient
    return GitHubAPIClient()


# ---------------------------------------------------------------------------
# Tree fetching
# ---------------------------------------------------------------------------

def get_repo_tree(repo: str, base_commit: str, use_cache: bool = True) -> List[str]:
    """
    Lấy danh sách file paths của repo tại base_commit.

    Sử dụng GitHub API: GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1
    Kết quả được cache trên disk tại TREE_CACHE_DIR.

    Returns:
        List[str]: Danh sách file paths đã lọc (không binary, không junk).
        Trả về [] nếu không lấy được.
    """
    os.makedirs(TREE_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(TREE_CACHE_DIR, f"{_slug(repo)}_{_commit8(base_commit)}.json")

    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                logger.info(f"[RepoProvider] Tree cache hit: {repo}@{base_commit[:8]} ({len(cached)} paths)")
                return cached
        except Exception as e:
            logger.warning(f"[RepoProvider] Failed to read tree cache {cache_path}: {e}")

    # Fetch từ GitHub API
    try:
        client = _get_github_client()
        endpoint = f"repos/{repo}/git/trees/{base_commit}?recursive=1"
        logger.info(f"[RepoProvider] Fetching git tree: {repo}@{base_commit[:8]}...")
        result = client.get(endpoint)
        if not result:
            logger.warning(f"[RepoProvider] Empty response for tree: {repo}@{base_commit[:8]}")
            return []

        raw_tree = result.get("tree", [])
        # Chỉ lấy blob (file), không lấy tree (directory)
        all_paths = [
            item["path"] for item in raw_tree
            if item.get("type") == "blob" and item.get("path")
        ]

        # Lọc bỏ paths không hữu ích
        filtered_paths = [p for p in all_paths if not _is_excluded(p)]

        # Ưu tiên source/test/config và giới hạn tối đa MAX_TREE_PATHS
        if len(filtered_paths) > MAX_TREE_PATHS:
            filtered_paths = _prioritize_paths(filtered_paths, MAX_TREE_PATHS)

        logger.info(f"[RepoProvider] Tree fetched: {len(all_paths)} total → {len(filtered_paths)} filtered paths")

        if use_cache:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(filtered_paths, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"[RepoProvider] Failed to save tree cache: {e}")

        return filtered_paths

    except Exception as e:
        logger.error(f"[RepoProvider] Error fetching tree for {repo}@{base_commit}: {e}")
        return []


def _prioritize_paths(paths: List[str], limit: int) -> List[str]:
    """
    Khi tree quá lớn, ưu tiên source code, tests, config, docs.
    Giữ tối đa `limit` paths.
    """
    priority_order = []
    rest = []
    for p in paths:
        lower = p.lower()
        if (
            p.endswith(".py") or p.endswith(".js") or p.endswith(".ts")
            or p.endswith(".java") or p.endswith(".go") or p.endswith(".rs")
            or p.endswith(".c") or p.endswith(".cpp") or p.endswith(".h")
            or "test" in lower or "spec" in lower
            or p.endswith(".cfg") or p.endswith(".ini") or p.endswith(".toml")
            or p.endswith(".yml") or p.endswith(".yaml")
            or p.endswith(".md") or p.endswith(".rst")
            or p.endswith(".txt")
        ):
            priority_order.append(p)
        else:
            rest.append(p)

    return (priority_order + rest)[:limit]


# ---------------------------------------------------------------------------
# File content fetching
# ---------------------------------------------------------------------------

def get_file_content(
    repo: str,
    path: str,
    base_commit: str,
    use_cache: bool = True,
    max_bytes: int = 200_000,
) -> Optional[str]:
    """
    Lấy nội dung file tại base_commit (KHÔNG phải HEAD).

    Sử dụng GitHub API: GET /repos/{owner}/{repo}/contents/{path}?ref={base_commit}
    Hoặc git blob API nếu cần.

    Returns:
        str: Nội dung text của file, hoặc None nếu lỗi/binary quá lớn.
    """
    os.makedirs(FILE_CACHE_DIR, exist_ok=True)
    cache_dir = os.path.join(FILE_CACHE_DIR, f"{_slug(repo)}_{_commit8(base_commit)}")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{_path_hash(path)}.json")

    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached.get("path") == path:
                    logger.debug(f"[RepoProvider] File cache hit: {repo}/{path}@{base_commit[:8]}")
                    return cached.get("content")
        except Exception as e:
            logger.warning(f"[RepoProvider] Failed to read file cache {cache_path}: {e}")

    # Fetch từ GitHub API
    try:
        client = _get_github_client()
        endpoint = f"repos/{repo}/contents/{path}"
        result = client.get(endpoint, params={"ref": base_commit})

        if not result:
            logger.warning(f"[RepoProvider] File not found: {repo}/{path}@{base_commit[:8]}")
            return None

        encoding = result.get("encoding", "")
        content_b64 = result.get("content", "")
        size = result.get("size", 0)

        if size > max_bytes:
            logger.warning(f"[RepoProvider] File too large ({size} bytes), skipping: {path}")
            return None

        if encoding == "base64" and content_b64:
            try:
                raw_bytes = base64.b64decode(content_b64.replace("\n", ""))
                text = raw_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                logger.warning(f"[RepoProvider] Failed to decode file {path}: {e}")
                return None
        else:
            text = result.get("content", "")

        if not text:
            return None

        # Kiểm tra binary: nếu có quá nhiều null bytes thì bỏ
        null_count = text.count("\x00")
        if null_count > len(text) * 0.05:
            logger.warning(f"[RepoProvider] File appears binary, skipping: {path}")
            return None

        # Cache result
        if use_cache:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump({"path": path, "content": text, "repo": repo, "commit": base_commit}, f, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"[RepoProvider] Failed to save file cache: {e}")

        logger.debug(f"[RepoProvider] Fetched file: {repo}/{path}@{base_commit[:8]} ({len(text)} chars)")
        return text

    except Exception as e:
        logger.error(f"[RepoProvider] Error fetching {repo}/{path}@{base_commit}: {e}")
        return None
