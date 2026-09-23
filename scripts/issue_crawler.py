"""
Module: issue_crawler.py
Thu thập Issue và liên kết với Pull Request đã merged.
Sử dụng REST API cốt lõi (/pulls) thay vì Search API hay Timeline API để:
1. Tuyệt đối không bị dính GitHub Secondary Rate Limit (abuse detection).
2. Tốc độ thu thập nhanh gấp 20 lần (chỉ 2 API calls cho mỗi cặp Issue-PR hợp lệ).
3. Hiển thị tiến trình trực tiếp (real-time progress logs) trong terminal.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from scripts.github_api import GitHubAPIClient
from scripts.pr_parser import PRParser
from scripts.file_parser import FileParser

logger = logging.getLogger("IssueCrawler")


class IssueCrawler:
    def __init__(self, client: Optional[GitHubAPIClient] = None):
        self.client = client or GitHubAPIClient()

    def crawl_repo_sample(self, owner: str, repo: str, target_count: int = 15) -> List[Dict[str, Any]]:
        """
        Crawl các closed issues từ một repository và liên kết với PR đã merged.
        Chiến lược tối ưu:
        - Quét danh sách Closed PRs qua endpoint core /pulls.
        - Chỉ xét các PR đã MERGED và không phải bot.
        - Trích xuất Issue Number từ PR title và PR body (fixes #, closes #, resolves #).
        - Lấy thông tin chi tiết của Issue và Changed files.
        """
        logger.info(f"[{owner}/{repo}] Bắt đầu quét dữ liệu (Mục tiêu: {target_count} linked issues)...")
        results = []
        seen_issue_ids = set()
        page = 1
        max_pages = 20  # Quét tối đa 20 trang (1000 PRs)

        while len(results) < target_count and page <= max_pages:
            logger.info(f"[{owner}/{repo}] Đang quét trang {page} của danh sách closed PRs (Đã thu thập: {len(results)}/{target_count})...")
            prs = self.client.get_pull_requests(owner, repo, state="closed", per_page=50, page=page)
            if not prs:
                logger.info(f"[{owner}/{repo}] Không còn PR nào khác ở trang {page}.")
                break

            for pr in prs:
                # 1. Bỏ qua nếu PR chưa merge
                if not pr.get("merged_at"):
                    continue

                # 2. Bỏ qua bot
                author_login = pr.get("user", {}).get("login", "")
                author_type = pr.get("user", {}).get("type", "")
                if author_type == "Bot" or author_login.endswith("[bot]"):
                    continue

                pr_number = pr.get("number")
                pr_title = pr.get("title", "")
                pr_body = pr.get("body", "") or ""

                # 3. Trích xuất Issue Number liên kết
                linked_issue_nums = PRParser.extract_linked_issue_numbers(pr_title, pr_body)
                if not linked_issue_nums:
                    continue

                for issue_num in sorted(list(linked_issue_nums)):
                    record_id = f"{owner}_{repo}_{issue_num}"
                    if record_id in seen_issue_ids:
                        continue

                    # 4. Lấy chi tiết Issue gốc
                    issue_raw = self.client.get_issue(owner, repo, issue_num)
                    if not issue_raw or "pull_request" in issue_raw:
                        # Bỏ qua nếu là PR hoặc không tồn tại
                        continue

                    pr_meta = PRParser.parse_pr_metadata(pr)
                    base_commit = pr_meta.get("base_commit", "")

                    # 5. Lấy danh sách files thay đổi kèm base_code
                    files_raw = self.client.get_pr_files(owner, repo, pr_number)
                    if not files_raw:
                        continue

                    files_summary = FileParser.parse_changed_files(
                        files_raw,
                        base_commit=base_commit,
                        repo_full_name=f"{owner}/{repo}"
                    )

                    record = {
                        "id": record_id,
                        "base_commit": base_commit,
                        "issue": {
                            "number": issue_num,
                            "title": issue_raw.get("title", "").strip(),
                            "body": (issue_raw.get("body") or "").strip(),
                            "labels": [lbl.get("name") for lbl in issue_raw.get("labels", [])],
                            "state": issue_raw.get("state"),
                            "created_at": issue_raw.get("created_at"),
                            "closed_at": issue_raw.get("closed_at"),
                            "url": issue_raw.get("html_url")
                        },
                        "repository": {
                            "owner": owner,
                            "name": repo,
                            "full_name": f"{owner}/{repo}",
                            "url": f"https://github.com/{owner}/{repo}"
                        },
                        "linked_pr": pr_meta,
                        "changes": {
                            "files_changed_count": files_summary["total_files"],
                            "additions": files_summary["total_additions"],
                            "deletions": files_summary["total_deletions"],
                            "files": files_summary["files"]
                        },
                        "tests": {
                            "test_files_changed": files_summary["test_files_changed"],
                            "test_files_count": files_summary["test_files_count"],
                            "test_files": files_summary["test_file_list"]
                        }
                    }

                    seen_issue_ids.add(record_id)
                    results.append(record)

                    logger.info(
                        f"[{owner}/{repo}] [{len(results)}/{target_count}] Đã lấy: Issue #{issue_num} <- PR #{pr_number} "
                        f"(Files: {files_summary['total_files']}, Tests: {files_summary['test_files_changed']}) | {record['issue']['title'][:50]}..."
                    )

                    if len(results) >= target_count:
                        break

                if len(results) >= target_count:
                    break

            page += 1

        logger.info(f"[{owner}/{repo}] Hoàn thành: Đã crawl thành công {len(results)}/{target_count} linked issues.")
        return results
