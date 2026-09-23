"""
CLI Script: crawl_dataset.py
Thu thập dataset từ các repo mục tiêu và lưu vào thư mục data/raw/
Hỗ trợ cả chế độ thực tế (qua GitHub API) và chế độ mock mẫu (để chạy thử khi chưa có token).
"""

import os
import sys
import json
import argparse
import logging
from typing import List, Dict, Any

# Đảm bảo đường dẫn import hoạt động
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.github_api import GitHubAPIClient
from scripts.issue_crawler import IssueCrawler

logger = logging.getLogger("CrawlDataset")


SAMPLE_REPOS = [
    ("psf", "requests"),
    ("pallets", "flask"),
    ("encode", "django-rest-framework")
]


def generate_mock_raw_data() -> List[Dict[str, Any]]:
    """Tạo dữ liệu mẫu đa dạng 4 trục phục vụ thử nghiệm pipeline nhanh kèm base_commit và base_code."""
    return [
        {
            "id": "psf_requests_4175",
            "base_commit": "a4f89d38c64d8a1c92518e1b6f0e4b85994f2711",
            "issue": {
                "number": 4175,
                "title": "Session.send should not mutate request headers when prepared request is passed",
                "body": "When passing an already prepared request into `Session.send()`, headers are modified in-place causing subsequent retries to fail with duplicate or corrupted headers. Minimal repro:\n```python\ns = requests.Session()\nreq = s.prepare_request(requests.Request('GET', 'http://httpbin.org/get', headers={'X-Custom': '1'}))\ns.send(req)\n```",
                "labels": ["bug", "headers"],
                "state": "closed",
                "created_at": "2023-01-10T08:00:00Z",
                "closed_at": "2023-01-12T14:00:00Z",
                "url": "https://github.com/psf/requests/issues/4175"
            },
            "repository": {
                "owner": "psf",
                "name": "requests",
                "full_name": "psf/requests",
                "url": "https://github.com/psf/requests"
            },
            "linked_pr": {
                "pr_number": 4182,
                "pr_title": "Fix in-place mutation of prepared request headers in Session.send",
                "pr_body": "Closes #4175. Ensures a shallow copy of headers is made before applying session defaults.",
                "pr_url": "https://github.com/psf/requests/pull/4182",
                "state": "closed",
                "merged": True,
                "merged_at": "2023-01-12T13:55:00Z",
                "base_branch": "main",
                "head_branch": "fix-header-mutation",
                "base_commit": "a4f89d38c64d8a1c92518e1b6f0e4b85994f2711",
                "base_commit_url": "https://github.com/psf/requests/commit/a4f89d38c64d8a1c92518e1b6f0e4b85994f2711",
                "head_commit": "c8e2193bfa78e50b32087ca393e4f3ca4a1cc2a6",
                "merge_commit_sha": "d991ef23ba11c784992bb3024856aef192bca711",
                "author": "dev_contributor",
                "is_bot": False
            },
            "changes": {
                "files_changed_count": 2,
                "additions": 14,
                "deletions": 3,
                "files": [
                    {
                        "filename": "requests/sessions.py",
                        "status": "modified",
                        "additions": 8,
                        "deletions": 3,
                        "changes": 11,
                        "is_test": False,
                        "is_source": True,
                        "is_doc": False,
                        "is_comment_only": False,
                        "patch_snippet": "@@ -640,7 +640,11 @@ class Session(object):\n-        request.headers.update(self.headers)\n+        headers = request.headers.copy()\n+        headers.update(self.headers)\n+        request.headers = headers",
                        "base_code": "class Session(object):\n        request.headers.update(self.headers)",
                        "base_file_url": "https://github.com/psf/requests/blob/a4f89d38c64d8a1c92518e1b6f0e4b85994f2711/requests/sessions.py"
                    },
                    {
                        "filename": "tests/test_requests.py",
                        "status": "modified",
                        "additions": 6,
                        "deletions": 0,
                        "changes": 6,
                        "is_test": True,
                        "is_source": False,
                        "is_doc": False,
                        "is_comment_only": False,
                        "patch_snippet": "@@ -120,6 +120,12 @@ def test_session():\n+def test_session_send_does_not_mutate_headers():\n+    s = requests.Session()\n+    req = s.prepare_request(requests.Request('GET', 'http://httpbin.org/get'))\n+    s.send(req)\n+    assert 'X-Custom' not in req.headers",
                        "base_code": "def test_session():",
                        "base_file_url": "https://github.com/psf/requests/blob/a4f89d38c64d8a1c92518e1b6f0e4b85994f2711/tests/test_requests.py"
                    }
                ]
            },
            "tests": {
                "test_files_changed": True,
                "test_files_count": 1,
                "test_files": ["tests/test_requests.py"]
            }
        },
        {
            "id": "pallets_flask_3922",
            "base_commit": "b2c91834920dfa561129ae35c7a9e10fa4e27f08",
            "issue": {
                "number": 3922,
                "title": "url_for raises KeyError when endpoint not found with subdomains",
                "body": "Calling url_for with a nonexistent endpoint when SUBDOMAIN_MATCHing is enabled throws unhandled KeyError instead of BuildError. Expected behavior is to raise BuildError according to Werkzeug spec.",
                "labels": ["bug", "routing"],
                "state": "closed",
                "created_at": "2023-02-01T10:00:00Z",
                "closed_at": "2023-02-02T16:00:00Z",
                "url": "https://github.com/pallets/flask/issues/3922"
            },
            "repository": {
                "owner": "pallets",
                "name": "flask",
                "full_name": "pallets/flask",
                "url": "https://github.com/pallets/flask"
            },
            "linked_pr": {
                "pr_number": 3925,
                "pr_title": "Catch KeyError and raise BuildError in url_for with subdomains",
                "pr_body": "Fixes #3922. Properly delegates URL building exception.",
                "pr_url": "https://github.com/pallets/flask/pull/3925",
                "state": "closed",
                "merged": True,
                "merged_at": "2023-02-02T15:50:00Z",
                "base_branch": "main",
                "head_branch": "fix-url-for-subdomain",
                "base_commit": "b2c91834920dfa561129ae35c7a9e10fa4e27f08",
                "base_commit_url": "https://github.com/pallets/flask/commit/b2c91834920dfa561129ae35c7a9e10fa4e27f08",
                "head_commit": "e818a7c81729bfa81903429bbcca83719028cb55",
                "merge_commit_sha": "f1092837bcba1298471629485718a29bca019283",
                "author": "flask_dev",
                "is_bot": False
            },
            "changes": {
                "files_changed_count": 2,
                "additions": 9,
                "deletions": 2,
                "files": [
                    {
                        "filename": "src/flask/helpers.py",
                        "status": "modified",
                        "additions": 4,
                        "deletions": 2,
                        "changes": 6,
                        "is_test": False,
                        "is_source": True,
                        "is_doc": False,
                        "is_comment_only": False,
                        "patch_snippet": "@@ -310,4 +310,6 @@ def url_for(endpoint, **values):\n-    rv = url_adapter.build(endpoint, values)\n+    try:\n+        rv = url_adapter.build(endpoint, values)\n+    except KeyError as e:\n+        raise BuildError(endpoint, values, 'GET') from e",
                        "base_code": "def url_for(endpoint, **values):\n    rv = url_adapter.build(endpoint, values)",
                        "base_file_url": "https://github.com/pallets/flask/blob/b2c91834920dfa561129ae35c7a9e10fa4e27f08/src/flask/helpers.py"
                    },
                    {
                        "filename": "tests/test_helpers.py",
                        "status": "modified",
                        "additions": 5,
                        "deletions": 0,
                        "changes": 5,
                        "is_test": True,
                        "is_source": False,
                        "is_doc": False,
                        "is_comment_only": False,
                        "patch_snippet": "@@ -55,0 +55,5 @@ def test_url_for_subdomain_error():\n+def test_url_for_subdomain_error():\n+    with pytest.raises(BuildError):\n+        url_for('nonexistent')",
                        "base_code": "",
                        "base_file_url": "https://github.com/pallets/flask/blob/b2c91834920dfa561129ae35c7a9e10fa4e27f08/tests/test_helpers.py"
                    }
                ]
            },
            "tests": {
                "test_files_changed": True,
                "test_files_count": 1,
                "test_files": ["tests/test_helpers.py"]
            }
        },
        {
            "id": "encode_django-rest-framework_5832",
            "base_commit": "c3e1092837492817294857102938475619283749",
            "issue": {
                "number": 5832,
                "title": "CSRF token disclosure vulnerability in SessionAuthentication during exception handling",
                "body": "When an unhandled exception occurs in an APIView, SessionAuthentication fails to clear the CSRF cookie or leaks sensitive session headers in the error response payload, leading to potential token leakage under specific CORS configurations. Need to enforce strict header stripping in exception handler.",
                "labels": ["security", "authentication"],
                "state": "closed",
                "created_at": "2023-03-05T09:00:00Z",
                "closed_at": "2023-03-07T11:00:00Z",
                "url": "https://github.com/encode/django-rest-framework/issues/5832"
            },
            "repository": {
                "owner": "encode",
                "name": "django-rest-framework",
                "full_name": "encode/django-rest-framework",
                "url": "https://github.com/encode/django-rest-framework"
            },
            "linked_pr": {
                "pr_number": 5835,
                "pr_title": "Sanitize session headers and prevent CSRF disclosure on view exception",
                "pr_body": "Resolves #5832. Adds sanitization layer in exception_handler to strip sensitive auth headers.",
                "pr_url": "https://github.com/encode/django-rest-framework/pull/5835",
                "state": "closed",
                "merged": True,
                "merged_at": "2023-03-07T10:45:00Z",
                "base_branch": "master",
                "head_branch": "fix-csrf-leak",
                "base_commit": "c3e1092837492817294857102938475619283749",
                "base_commit_url": "https://github.com/encode/django-rest-framework/commit/c3e1092837492817294857102938475619283749",
                "head_commit": "a189283746192837461928374619283746192837",
                "merge_commit_sha": "d091827364519283746192837461928374619283",
                "author": "sec_researcher",
                "is_bot": False
            },
            "changes": {
                "files_changed_count": 3,
                "additions": 45,
                "deletions": 8,
                "files": [
                    {
                        "filename": "rest_framework/views.py",
                        "status": "modified",
                        "additions": 18,
                        "deletions": 5,
                        "changes": 23,
                        "is_test": False,
                        "is_source": True,
                        "is_doc": False,
                        "is_comment_only": False,
                        "patch_snippet": "@@ -80,5 +80,10 @@ def handle_exception(self, exc):\n-    response = exception_handler(exc, context)\n+    response = exception_handler(exc, context)\n+    if response is not None:\n+        response = sanitize_auth_headers(response)",
                        "base_code": "def handle_exception(self, exc):\n    response = exception_handler(exc, context)",
                        "base_file_url": "https://github.com/encode/django-rest-framework/blob/c3e1092837492817294857102938475619283749/rest_framework/views.py"
                    },
                    {
                        "filename": "rest_framework/authentication.py",
                        "status": "modified",
                        "additions": 12,
                        "deletions": 3,
                        "changes": 15,
                        "is_test": False,
                        "is_source": True,
                        "is_doc": False,
                        "is_comment_only": False,
                        "patch_snippet": "@@ -120,3 +120,8 @@ class SessionAuthentication:\n-    def enforce_csrf(self, request):\n+    def enforce_csrf(self, request):\n+        check_session_validity(request)",
                        "base_code": "class SessionAuthentication:\n    def enforce_csrf(self, request):",
                        "base_file_url": "https://github.com/encode/django-rest-framework/blob/c3e1092837492817294857102938475619283749/rest_framework/authentication.py"
                    },
                    {
                        "filename": "tests/test_authentication.py",
                        "status": "modified",
                        "additions": 15,
                        "deletions": 0,
                        "changes": 15,
                        "is_test": True,
                        "is_source": False,
                        "is_doc": False,
                        "is_comment_only": False,
                        "patch_snippet": "@@ -200,0 +200,8 @@ def test_csrf_not_leaked():\n+def test_csrf_not_leaked():\n+    client = APIClient()\n+    res = client.get('/error-view')\n+    assert 'Set-Cookie' not in res.headers",
                        "base_code": "",
                        "base_file_url": "https://github.com/encode/django-rest-framework/blob/c3e1092837492817294857102938475619283749/tests/test_authentication.py"
                    }
                ]
            },
            "tests": {
                "test_files_changed": True,
                "test_files_count": 1,
                "test_files": ["tests/test_authentication.py"]
            }
        },
        # Mẫu một issue không đạt (Spam/Doc-only) để test bộ làm sạch
        {
            "id": "psf_requests_9999_invalid_doc",
            "base_commit": "e991827364519283746192837461928374619283",
            "issue": {
                "number": 9999,
                "title": "Fix typo in README",
                "body": "Fixed typo 'requsts' to 'requests'.",
                "labels": ["documentation"],
                "state": "closed",
                "created_at": "2023-04-01T00:00:00Z",
                "closed_at": "2023-04-01T01:00:00Z",
                "url": "https://github.com/psf/requests/issues/9999"
            },
            "repository": {
                "owner": "psf",
                "name": "requests",
                "full_name": "psf/requests",
                "url": "https://github.com/psf/requests"
            },
            "linked_pr": {
                "pr_number": 9999,
                "pr_title": "Fix typo in README",
                "pr_body": "Closes #9999",
                "pr_url": "https://github.com/psf/requests/pull/9999",
                "state": "closed",
                "merged": True,
                "merged_at": "2023-04-01T01:00:00Z",
                "base_branch": "main",
                "head_branch": "fix-typo",
                "base_commit": "e991827364519283746192837461928374619283",
                "base_commit_url": "https://github.com/psf/requests/commit/e991827364519283746192837461928374619283",
                "head_commit": "f001827364519283746192837461928374619283",
                "merge_commit_sha": "a111827364519283746192837461928374619283",
                "author": "typo_fixer",
                "is_bot": False
            },
            "changes": {
                "files_changed_count": 1,
                "additions": 1,
                "deletions": 1,
                "files": [
                    {
                        "filename": "README.md",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 1,
                        "changes": 2,
                        "is_test": False,
                        "is_source": False,
                        "is_doc": True,
                        "is_comment_only": False,
                        "patch_snippet": "@@ -1,2 +1,2 @@\n-requsts\n+requests",
                        "base_code": "requsts",
                        "base_file_url": "https://github.com/psf/requests/blob/e991827364519283746192837461928374619283/README.md"
                    }
                ]
            },
            "tests": {
                "test_files_changed": False,
                "test_files_count": 0,
                "test_files": []
            }
        }
    ]


def main():
    parser = argparse.ArgumentParser(description="RAAC GitHub Issue Crawler")
    parser.add_argument("--repos", nargs="+", help="Owner/Repo list, ví dụ: psf/requests pallets/flask")
    parser.add_argument("--limit", type=int, default=10, help="Số lượng issue mục tiêu cho mỗi repo (default: 10)")
    parser.add_argument("--output-dir", default="data/raw", help="Thư mục xuất dữ liệu (default: data/raw)")
    parser.add_argument("--mock", action="store_true", help="Chạy chế độ sinh dữ liệu mẫu giả lập (không cần mạng/token)")

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    if args.mock:
        logger.info("Running in MOCK mode: generating pre-validated synthetic issues...")
        mock_data = generate_mock_raw_data()
        out_file = os.path.join(args.output_dir, "mock_crawled_issues.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(mock_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(mock_data)} mock issues to {out_file}")
        return

    client = GitHubAPIClient()
    client.check_rate_limit()
    crawler = IssueCrawler(client)

    repos_to_crawl = []
    if args.repos:
        for r in args.repos:
            parts = r.split("/")
            if len(parts) == 2:
                repos_to_crawl.append((parts[0], parts[1]))
            else:
                logger.error(f"Invalid repo format: '{r}'. Expected 'owner/repo'.")
    else:
        repos_to_crawl = SAMPLE_REPOS

    all_collected = []
    for owner, repo in repos_to_crawl:
        try:
            records = crawler.crawl_repo_sample(owner, repo, target_count=args.limit)
            all_collected.extend(records)
            repo_file = os.path.join(args.output_dir, f"{owner}_{repo}_issues.json")
            with open(repo_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(records)} issues to {repo_file}")
        except Exception as e:
            logger.error(f"Error crawling {owner}/{repo}: {e}")

    total_file = os.path.join(args.output_dir, "all_crawled_raw.json")
    with open(total_file, "w", encoding="utf-8") as f:
        json.dump(all_collected, f, indent=2, ensure_ascii=False)
    logger.info(f"Crawl complete. Total issues saved: {len(all_collected)} -> {total_file}")


if __name__ == "__main__":
    main()
