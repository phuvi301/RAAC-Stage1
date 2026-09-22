"""
Module: clean_dataset.py
Triển khai Task 1.4: Làm sạch dataset theo đúng tiêu chí tại docs/filter_rules.md:
- Loại bỏ Duplicate, Spam, Bot.
- Loại bỏ Issue quá ngắn / mơ hồ.
- Loại bỏ PR doc-only, zero-code-change, unmerged.
- Tránh over-cleaning: Giữ các issue đơn giản có code change (C=1, I=1).
- Xuất dữ liệu sạch vào data/cleaned/ và báo cáo thống kê lọc.
"""

import os
import sys
import json
import argparse
import logging
from typing import List, Dict, Any, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger("CleanDataset")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


from scripts.file_parser import FileParser


class DatasetCleaner:
    MIN_BODY_WORDS = 5
    SPAM_TITLES = {"bug", "not working", "please fix", "help", "error", "test"}
    DOC_PR_PREFIXES = (
        "docs:", "doc:", "documentation:", "docs(", "typo:", "typos:",
        "chore(doc):", "chore(docs):", "style(doc):", "style(docs):"
    )

    def __init__(self, blacklist_path: str = "data/blacklist_issues.json"):
        self.stats = {
            "total_raw": 0,
            "kept": 0,
            "rejected_duplicate": 0,
            "rejected_bot": 0,
            "rejected_short_or_spam": 0,
            "rejected_no_merged_pr": 0,
            "rejected_no_code_change": 0,
            "rejected_doc_only": 0,
            "rejected_blacklist": 0,
            "rejected_reasons": {}
        }
        self.blacklist = self._load_blacklist(blacklist_path)

    def _load_blacklist(self, path: str) -> Dict[str, str]:
        """Tải danh sách blacklist thủ công nếu có."""
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {item: "Manually blacklisted" for item in data if not str(item).startswith("_")}
                elif isinstance(data, dict):
                    return {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception as e:
            logger.warning(f"Failed to load blacklist from {path}: {e}")
        return {}

    def is_valid_issue(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        rec_id = record.get("id", "")

        # 0. Kiểm tra blacklist thủ công
        if rec_id in self.blacklist:
            return False, f"Blacklisted: {self.blacklist[rec_id]}"

        issue = record.get("issue", {})
        title = (issue.get("title") or "").strip()
        body = (issue.get("body") or "").strip()
        pr = record.get("linked_pr", {})
        pr_title = (pr.get("pr_title") or "").strip().lower()
        changes = record.get("changes", {})
        tests = record.get("tests", {})

        # 1. Kiểm tra PR đã merge chưa
        if not pr.get("merged", False):
            return False, "PR not merged"

        # 2. Kiểm tra bot
        if pr.get("is_bot", False):
            return False, "PR authored by automated bot"

        # 3. Kiểm tra spam/quá ngắn
        if title.lower() in self.SPAM_TITLES and len(body) < 30:
            return False, "Title too generic with insufficient body"

        total_words = len((title + " " + body).split())
        if total_words < self.MIN_BODY_WORDS:
            return False, f"Issue text too short ({total_words} words < {self.MIN_BODY_WORDS})"

        # 4. Kiểm tra có code change thực chất không (loại bỏ doc-only)
        files = changes.get("files", [])
        if not files:
            return False, "Zero changed files"

        source_or_test_files = [f for f in files if f.get("is_source") or f.get("is_test")]
        if not source_or_test_files:
            return False, "Documentation-only (no source or test files changed)"

        total_lines = changes.get("additions", 0) + changes.get("deletions", 0)
        if total_lines == 0:
            return False, "Zero lines added or deleted"

        has_test_files = tests.get("test_files_changed", False) or any(f.get("is_test") for f in files)

        # 5. Kiểm tra tiền tố PR title mang tính doc-only / typo fix khi không kèm test
        if any(pr_title.startswith(p) for p in self.DOC_PR_PREFIXES) and not has_test_files:
            return False, f"PR title indicates doc/typo fix only ('{pr.get('pr_title', '')}') with no tests"

        # 6. Kiểm tra in-code doc/comment changes (sửa comment/docstring trong file .py/code)
        if not has_test_files:
            all_source_files_are_comment_only = True
            for f in source_or_test_files:
                if f.get("is_test"):
                    all_source_files_are_comment_only = False
                    break
                # Nếu file có patch_snippet, phân tích xem có phải 100% comment/docstring không
                patch = f.get("patch_snippet", "")
                is_comment = f.get("is_comment_only", False) or FileParser.is_comment_or_doc_patch(patch)
                if not is_comment:
                    all_source_files_are_comment_only = False
                    break

            if all_source_files_are_comment_only:
                return False, "In-code docstring or comment-only change (no substantive logic change)"

        return True, "Valid"

    def clean(self, raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.stats["total_raw"] = len(raw_records)
        cleaned = []
        seen_ids = set()

        for rec in raw_records:
            rec_id = rec.get("id")

            # Xử lý Duplicate
            if rec_id in seen_ids:
                self.stats["rejected_duplicate"] += 1
                self._record_reason("Duplicate Issue ID")
                continue

            is_valid, reason = self.is_valid_issue(rec)
            if is_valid:
                seen_ids.add(rec_id)
                cleaned.append(rec)
            else:
                self._record_reason(reason)
                reason_lower = reason.lower()
                if "blacklist" in reason_lower:
                    self.stats["rejected_blacklist"] += 1
                elif "bot" in reason_lower:
                    self.stats["rejected_bot"] += 1
                elif "short" in reason_lower or "generic" in reason_lower:
                    self.stats["rejected_short_or_spam"] += 1
                elif "merged" in reason_lower:
                    self.stats["rejected_no_merged_pr"] += 1
                elif "doc" in reason_lower or "comment" in reason_lower or "typo" in reason_lower:
                    self.stats["rejected_doc_only"] += 1
                elif "code" in reason_lower or "lines" in reason_lower:
                    self.stats["rejected_no_code_change"] += 1

        self.stats["kept"] = len(cleaned)
        return cleaned

    def _record_reason(self, reason: str):
        self.stats["rejected_reasons"][reason] = self.stats["rejected_reasons"].get(reason, 0) + 1

    def print_report(self):
        logger.info("=" * 65)
        logger.info("DATA CLEANING SUMMARY REPORT (RAAC BENCHMARK)")
        logger.info("=" * 65)
        logger.info(f"Total raw issues processed: {self.stats['total_raw']}")
        logger.info(f"Accepted / Kept issues:     {self.stats['kept']}")
        logger.info(f"Rejected issues:            {self.stats['total_raw'] - self.stats['kept']}")
        logger.info("-" * 65)
        logger.info("Rejection categories:")
        logger.info(f"  - Duplicate:                {self.stats['rejected_duplicate']}")
        logger.info(f"  - Unmerged PR:              {self.stats['rejected_no_merged_pr']}")
        logger.info(f"  - Bot Author:               {self.stats['rejected_bot']}")
        logger.info(f"  - Short / Spam / Vague:     {self.stats['rejected_short_or_spam']}")
        logger.info(f"  - Doc-only / Comment-only:  {self.stats['rejected_doc_only']}")
        logger.info(f"  - Zero code changes:        {self.stats['rejected_no_code_change']}")
        logger.info(f"  - Manual Blacklist:         {self.stats['rejected_blacklist']}")
        logger.info("-" * 65)
        logger.info("Detailed rejection reasons:")
        for r, count in self.stats["rejected_reasons"].items():
            logger.info(f"  • {r}: {count}")
        logger.info("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Clean raw issues into normalized benchmark")
    parser.add_argument("--input", default="data/raw/all_crawled_raw.json", help="Path to raw JSON file")
    parser.add_argument("--output", default="data/cleaned/cleaned_benchmark.json", help="Path to cleaned output JSON")
    parser.add_argument("--blacklist", default="data/blacklist_issues.json", help="Path to manual blacklist JSON")
    args = parser.parse_args()

    input_file = args.input
    # Fallback to mock file if all_crawled_raw.json doesn't exist yet
    if not os.path.exists(input_file):
        mock_path = "data/raw/mock_crawled_issues.json"
        if os.path.exists(mock_path):
            input_file = mock_path
            logger.info(f"Defaulting to mock data at {mock_path}")
        else:
            logger.error(f"Input file not found: {args.input}. Run crawl_dataset.py first!")
            return

    with open(input_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    cleaner = DatasetCleaner(blacklist_path=args.blacklist)
    cleaned_data = cleaner.clean(raw_data)
    cleaner.print_report()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Cleaned dataset saved successfully to {args.output}")


if __name__ == "__main__":
    main()
