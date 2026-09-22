"""
Module: github_api.py
Chịu trách nhiệm tương tác với GitHub REST API, xử lý authentication,
quản lý Rate Limit (cả Primary và Secondary Rate Limit), phân trang và tự động retry.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GitHubAPI")


class GitHubAPIClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, request_delay: float = 0.4):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.request_delay = request_delay
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RAAC-Benchmark-Crawler/1.0"
        })
        if self.token and self.token != "your_github_personal_access_token_here":
            self.session.headers.update({"Authorization": f"token {self.token}"})
            logger.info("GitHub API initialized with personal access token.")
        else:
            logger.warning("No GitHub Token provided. Unauthenticated rate limit is 60 requests/hour!")

    def check_rate_limit(self) -> Dict[str, Any]:
        """Kiểm tra số lượng request còn lại của token."""
        url = f"{self.BASE_URL}/rate_limit"
        resp = self.session.get(url)
        if resp.status_code == 200:
            core = resp.json().get("resources", {}).get("core", {})
            remaining = core.get("remaining", 0)
            limit = core.get("limit", 0)
            reset_time = core.get("reset", 0)
            logger.info(f"Rate Limit: {remaining}/{limit} requests remaining (Resets at timestamp {reset_time})")
            return core
        return {}

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 5) -> Optional[Any]:
        """Gửi GET request với tự động retry, xử lý Primary & Secondary Rate Limit."""
        url = endpoint if endpoint.startswith("http") else f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        params = params or {}

        for attempt in range(1, max_retries + 1):
            try:
                # Throttling nhẹ nhàng giữa các requests để tránh kích hoạt Secondary Rate Limit
                if self.request_delay > 0:
                    time.sleep(self.request_delay)

                response = self.session.get(url, params=params, timeout=30)

                # Xử lý Secondary Rate Limit (Abuse / Burst Detection)
                if response.status_code in (403, 429):
                    resp_text = response.text.lower()
                    retry_after = response.headers.get("Retry-After")
                    reset_header = response.headers.get("X-RateLimit-Reset")

                    if "secondary rate limit" in resp_text:
                        wait_sec = int(retry_after) if retry_after else 45
                        logger.warning(f"GitHub Secondary Rate Limit hit! Chờ {wait_sec}s để tiếp tục...")
                        time.sleep(wait_sec)
                        continue

                    # Primary Rate limit chạm ngưỡng
                    if reset_header:
                        sleep_seconds = max(int(reset_header) - int(time.time()) + 2, 10)
                        logger.warning(f"Primary Rate limit hit! Chờ {sleep_seconds}s cho đến khi reset...")
                        time.sleep(sleep_seconds)
                        continue

                    logger.warning("Forbidden / Rate limited. Chờ 30s...")
                    time.sleep(30)
                    continue

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.debug(f"Resource not found: {url}")
                    return None
                else:
                    logger.warning(f"Request failed ({response.status_code}): {response.text[:200]}")
                    time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error on {url} (Attempt {attempt}/{max_retries}): {e}")
                time.sleep(2 ** attempt)

        logger.error(f"Failed to fetch {url} after {max_retries} attempts.")
        return None

    def search_merged_prs_with_fixes(self, owner: str, repo: str, keyword: str = "fixes", per_page: int = 30, page: int = 1) -> List[Dict[str, Any]]:
        """Tìm kiếm các PR đã merged có chứa keyword đóng issue."""
        query = f"repo:{owner}/{repo} type:pr is:merged {keyword} -author:app/dependabot"
        endpoint = "/search/issues"
        params = {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": per_page,
            "page": page
        }
        res = self.get(endpoint, params=params)
        if isinstance(res, dict) and "items" in res:
            return res["items"]
        return []

    def get_pull_requests(self, owner: str, repo: str, state: str = "closed", per_page: int = 50, page: int = 1) -> List[Dict[str, Any]]:
        """Lấy danh sách PRs theo trang."""
        endpoint = f"/repos/{owner}/{repo}/pulls"
        params = {
            "state": state,
            "sort": "updated",
            "direction": "desc",
            "per_page": per_page,
            "page": page
        }
        res = self.get(endpoint, params=params)
        return res if isinstance(res, list) else []

    def get_issue(self, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một Issue."""
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}"
        return self.get(endpoint)

    def get_pull_request(self, owner: str, repo: str, pull_number: int) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một PR."""
        endpoint = f"/repos/{owner}/{repo}/pulls/{pull_number}"
        return self.get(endpoint)

    def get_pr_files(self, owner: str, repo: str, pull_number: int) -> List[Dict[str, Any]]:
        """Lấy danh sách các files thay đổi trong một PR."""
        endpoint = f"/repos/{owner}/{repo}/pulls/{pull_number}/files"
        res = self.get(endpoint, params={"per_page": 100})
        return res if isinstance(res, list) else []
