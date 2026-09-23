"""
Module: group_dataset_by_repo.py
Chuyển đổi dataset từ định dạng danh sách phẳng (flat list)
sang định dạng phân nhóm theo repository (grouped by repo):
{
  "dataset_version": "v1-genuine-hard",
  "repos": [
    {
      "repo": "owner/name",
      "repo_url": "https://github.com/owner/name",
      "issues": [
        {
          "id": "owner__name-number",
          "url": "https://github.com/owner/name/pull/number",
          "title": "...",
          "body": "...",
          "base_commit": "sha",
          "base_code": "..."
        }
      ]
    }
  ]
}
"""

import os
import sys
import json
import argparse
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GroupDataset")


def group_by_repo(
    records: List[Dict[str, Any]],
    dataset_version: str = "v1-genuine-hard",
    include_details: bool = True
) -> Dict[str, Any]:
    """Gom nhóm các issue theo từng repository."""
    repos_map: Dict[str, Dict[str, Any]] = {}

    for rec in records:
        repo_info = rec.get("repository", {})
        owner = repo_info.get("owner", "")
        repo_name = repo_info.get("name", "")
        full_name = repo_info.get("full_name") or f"{owner}/{repo_name}"
        repo_url = repo_info.get("url") or f"https://github.com/{full_name}"

        if full_name not in repos_map:
            repos_map[full_name] = {
                "repo": full_name,
                "repo_url": repo_url,
                "issues": []
            }

        issue = rec.get("issue", {})
        pr = rec.get("linked_pr", {})
        issue_num = issue.get("number", "")

        # Format id chuẩn: owner__repo-number hoặc giữ nguyên id gốc
        formatted_id = f"{owner}__{repo_name}-{issue_num}" if owner and repo_name and issue_num else rec.get("id", "")

        # Ưu tiên lấy PR URL nếu có, nếu không lấy issue URL
        target_url = pr.get("pr_url") or issue.get("url") or f"https://github.com/{full_name}/issues/{issue_num}"
        base_commit = rec.get("base_commit") or pr.get("base_commit", "")

        issue_entry: Dict[str, Any] = {
            "id": formatted_id,
            "url": target_url,
            "title": issue.get("title", "").strip(),
            "body": issue.get("body", "").strip(),
            "base_commit": base_commit
        }

        # Nếu include_details=True: đính kèm base_code và chi tiết thay đổi để AI chấm điểm tốt hơn
        if include_details:
            files = rec.get("changes", {}).get("files", [])
            base_code_snippets = []
            for f in files:
                bcode = f.get("base_code", "").strip()
                if bcode and (f.get("is_source") or f.get("is_test")):
                    base_code_snippets.append(f"File: `{f.get('filename')}`\n{bcode}")

            if base_code_snippets:
                issue_entry["base_code"] = "\n\n".join(base_code_snippets[:3])

            if "changes" in rec:
                issue_entry["changes"] = {
                    "files_changed_count": rec.get("changes", {}).get("files_changed_count", 0),
                    "additions": rec.get("changes", {}).get("additions", 0),
                    "deletions": rec.get("changes", {}).get("deletions", 0)
                }

        repos_map[full_name]["issues"].append(issue_entry)

    result = {
        "dataset_version": dataset_version,
        "total_repos": len(repos_map),
        "total_issues": sum(len(r["issues"]) for r in repos_map.values()),
        "repos": list(repos_map.values())
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Convert flat issues dataset to grouped-by-repo format")
    parser.add_argument("--input", default="data/cleaned/cleaned_benchmark.json", help="Đường dẫn file JSON đầu vào")
    parser.add_argument("--output", default="data/cleaned/cleaned_benchmark_grouped.json", help="Đường dẫn file JSON đầu ra")
    parser.add_argument("--version", default="v1-genuine-hard", help="Tên phiên bản dataset")
    parser.add_argument("--compact", action="store_true", help="Chỉ giữ đúng các trường tối giản (id, url, title, body, base_commit)")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not isinstance(records, list):
        logger.error(f"Expected a JSON list of records in {args.input}")
        return

    logger.info(f"Grouping {len(records)} records from {args.input}...")
    grouped = group_by_repo(records, dataset_version=args.version, include_details=not args.compact)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(grouped, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully exported {grouped['total_issues']} issues across {grouped['total_repos']} repos to {args.output}")


if __name__ == "__main__":
    main()
