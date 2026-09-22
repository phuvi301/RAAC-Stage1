"""
Module: check_dataset_bias.py
Kiểm tra và đánh giá mức độ Chống Thiên Lệch (Anti-bias / Selection Bias Audit)
của Benchmark Dataset trong nghiên cứu RAAC (Requirement-Aware Adaptive Collaboration).

Các khía cạnh kiểm tra:
1. Repository Distribution (Cân bằng giữa các kho mã nguồn)
2. LOC / Code Change Distribution (Đa dạng độ khó từ Micro đến Large)
3. Testability Distribution (Cân bằng giữa issue có test và không có test)
4. Category Diversity (Đa dạng loại yêu cầu: Bug fix, Feature, Refactor, Security)
5. Anti-bias Scorecard & Recommendations
"""

import os
import sys
import json
import argparse
from collections import Counter
from typing import List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class DatasetBiasChecker:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data
        self.total = len(data)

    def analyze_repositories(self) -> Dict[str, Any]:
        """Phân tích phân bố theo Repository."""
        repo_counts = Counter()
        for item in self.data:
            repo = item.get("repository", {}).get("full_name") or "unknown"
            repo_counts[repo] += 1

        results = []
        warnings = []
        for repo, count in repo_counts.most_common():
            pct = (count / self.total * 100) if self.total else 0
            results.append({
                "repo": repo,
                "count": count,
                "percentage": pct
            })
            if pct > 50.0:
                warnings.append(f"Repository '{repo}' chiếm áp đảo ({pct:.1f}% > 50%), nguy cơ Domain Bias.")
            elif pct < 10.0 and len(repo_counts) <= 4:
                warnings.append(f"Repository '{repo}' chiếm tỷ lệ thấp ({pct:.1f}% < 10%).")

        return {
            "counts": results,
            "unique_repos": len(repo_counts),
            "warnings": warnings
        }

    def analyze_loc_distribution(self) -> Dict[str, Any]:
        """Phân tích phân bố kích thước thay đổi (LOC: additions + deletions)."""
        bins = {
            "Micro (1-5 LOC)": 0,
            "Small (6-20 LOC)": 0,
            "Medium (21-100 LOC)": 0,
            "Large (>100 LOC)": 0
        }

        for item in self.data:
            changes = item.get("changes", {})
            total_lines = changes.get("additions", 0) + changes.get("deletions", 0)

            if total_lines <= 5:
                bins["Micro (1-5 LOC)"] += 1
            elif total_lines <= 20:
                bins["Small (6-20 LOC)"] += 1
            elif total_lines <= 100:
                bins["Medium (21-100 LOC)"] += 1
            else:
                bins["Large (>100 LOC)"] += 1

        warnings = []
        if bins["Micro (1-5 LOC)"] == 0:
            warnings.append("Thiếu các task đơn giản (Micro 1-5 LOC) để kiểm thử phân hệ cộng tác L1.")
        if bins["Large (>100 LOC)"] == 0:
            warnings.append("Thiếu các task quy mô lớn (>100 LOC) để kiểm thử phân hệ cộng tác L3/L4.")

        return {
            "bins": bins,
            "warnings": warnings
        }

    def analyze_testability(self) -> Dict[str, Any]:
        """Phân tích tỷ lệ PR có kèm unit test."""
        has_test_count = 0
        for item in self.data:
            tests = item.get("tests", {})
            if tests.get("test_files_changed", False) or tests.get("test_files_count", 0) > 0:
                has_test_count += 1

        no_test_count = self.total - has_test_count
        test_pct = (has_test_count / self.total * 100) if self.total else 0
        no_test_pct = (no_test_count / self.total * 100) if self.total else 0

        warnings = []
        if test_pct > 90.0:
            warnings.append(f"Tỷ lệ có test quá cao ({test_pct:.1f}%). Cần giữ thêm issue không có test để kiểm thử trục T (Testability).")
        elif test_pct < 30.0:
            warnings.append(f"Tỷ lệ có test quá thấp ({test_pct:.1f}%). Thiếu ground truth kiểm thử tự động.")

        return {
            "has_test_count": has_test_count,
            "no_test_count": no_test_count,
            "has_test_pct": test_pct,
            "no_test_pct": no_test_pct,
            "warnings": warnings
        }

    def analyze_categories(self) -> Dict[str, Any]:
        """Phân loại sơ bộ yêu cầu dựa trên từ khóa trong tiêu đề và nội dung."""
        categories = {
            "Bug Fix": 0,
            "Feature / Enhancement": 0,
            "Refactor / Performance": 0,
            "Security / CVE": 0,
            "Other": 0
        }

        for item in self.data:
            issue = item.get("issue", {})
            title = (issue.get("title") or "").lower()
            body = (issue.get("body") or "").lower()
            text = title + " " + body

            if any(k in text for k in ["cve", "vulnerability", "csrf", "xss", "security", "exploit", "sanitize"]):
                categories["Security / CVE"] += 1
            elif any(k in text for k in ["fix", "bug", "error", "fail", "crash", "exception", "traceback", "incorrect"]):
                categories["Bug Fix"] += 1
            elif any(k in text for k in ["add", "support", "feature", "new", "allow", "implement", "proposal"]):
                categories["Feature / Enhancement"] += 1
            elif any(k in text for k in ["refactor", "clean", "optimize", "speed", "perf", "simplify", "deprecated"]):
                categories["Refactor / Performance"] += 1
            else:
                categories["Other"] += 1

        return {
            "categories": categories
        }

    def generate_markdown_report(self) -> str:
        """Tạo báo cáo chi tiết chuẩn Markdown."""
        repo_data = self.analyze_repositories()
        loc_data = self.analyze_loc_distribution()
        test_data = self.analyze_testability()
        cat_data = self.analyze_categories()

        all_warnings = repo_data["warnings"] + loc_data["warnings"] + test_data["warnings"]

        lines = [
            "# Báo cáo Đánh giá Chống Thiên Lệch Dataset (Anti-bias Audit Report)",
            f"**Quy mô Benchmark hiện tại:** {self.total} issues",
            "",
            "---",
            "",
            "## 1. Phân bố theo Repository (Repository Balance)",
            "| Repository | Số lượng Issue | Tỷ lệ (%) |",
            "|---|---|---|"
        ]

        for r in repo_data["counts"]:
            lines.append(f"| `{r['repo']}` | {r['count']} | {r['percentage']:.1f}% |")

        lines.extend([
            "",
            "## 2. Phân bố Quy mô Thay đổi Mã nguồn (LOC Bins)",
            "Đo lường tính đa dạng độ phức tạp ($C$) và tác động kiến trúc ($I$):",
            "| Phân tầng kích thước | Số lượng Issue | Tỷ lệ (%) | Ý nghĩa đánh giá |",
            "|---|---|---|---|"
        ])

        desc_map = {
            "Micro (1-5 LOC)": "Bug nhỏ cục bộ (C=1, I=1), kiểm thử cộng tác L1",
            "Small (6-20 LOC)": "Tinh chỉnh logic đơn lẻ (C=2, I=1..2)",
            "Medium (21-100 LOC)": "Tính năng nhỏ / Sửa nhiều hàm (C=3, I=2..3)",
            "Large (>100 LOC)": "Tái cấu trúc / Kiến trúc sâu (C=4..5, I=4..5)"
        }

        for bin_name, count in loc_data["bins"].items():
            pct = (count / self.total * 100) if self.total else 0
            lines.append(f"| **{bin_name}** | {count} | {pct:.1f}% | {desc_map.get(bin_name, '')} |")

        lines.extend([
            "",
            "## 3. Phân bố Khả năng Kiểm thử (Testability Balance)",
            f"- **Số issue có Unit/Integration Test đi kèm:** {test_data['has_test_count']} ({test_data['has_test_pct']:.1f}%)",
            f"- **Số issue không có Test (cần manual/env test):** {test_data['no_test_count']} ({test_data['no_test_pct']:.1f}%)",
            "- *Nguyên tắc RAAC:* Giữ lại cả 2 nhóm để đo lường công bằng trục $T$ (Testability).",
            "",
            "## 4. Đa dạng Loại Yêu cầu (Category Diversity)",
            "| Danh mục | Số lượng | Tỷ lệ (%) |",
            "|---|---|---|"
        ])

        for cat_name, count in cat_data["categories"].items():
            pct = (count / self.total * 100) if self.total else 0
            lines.append(f"| {cat_name} | {count} | {pct:.1f}% |")

        lines.extend([
            "",
            "## 5. Đánh giá Tổng thể & Khuyến nghị (Anti-bias Scorecard)",
            f"- **Đa dạng nguồn:** {'[x] ĐẠT' if repo_data['unique_repos'] >= 3 else '[ ] CẦN BỔ SUNG'} (Hiện có {repo_data['unique_repos']} repositories)",
            f"- **Tránh độc quyền Repo:** {'[x] ĐẠT' if not any(r['percentage'] > 50.0 for r in repo_data['counts']) else '[ ] CẢNH BÁO'} (Không repo nào vượt 50%)",
            f"- **Bao phủ phổ điểm độ khó:** {'[x] ĐẠT' if len(loc_data['warnings']) == 0 else '[ ] CẢNH BÁO'} (Đầy đủ từ Micro đến Large)",
            f"- **Cân bằng Testability:** {'[x] ĐẠT' if len(test_data['warnings']) == 0 else '[ ] CẢNH BÁO'} (Có cả bài có test và không có test)",
            ""
        ])

        if all_warnings:
            lines.append("### ⚠️ Các điểm cần lưu ý hoàn thiện:")
            for w in all_warnings:
                lines.append(f"- {w}")
        else:
            lines.append("🎉 **Kết luận:** Bộ dữ liệu đạt chuẩn Chống Thiên Lệch (Unbiased Benchmark) theo Rubric RAAC Phase 1!")

        lines.append("")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Audit and check anti-bias metrics for RAAC benchmark dataset")
    parser.add_argument("--input", default="data/cleaned/cleaned_benchmark.json", help="Path to cleaned benchmark JSON")
    parser.add_argument("--report", default="docs/dataset_bias_report.md", help="Path to save markdown audit report")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    checker = DatasetBiasChecker(data)
    md_report = checker.generate_markdown_report()

    # In ra terminal
    print("\n" + "=" * 70)
    print("RAAC BENCHMARK - ANTI-BIAS AUDIT REPORT")
    print("=" * 70)
    print(md_report)
    print("=" * 70)

    # Lưu file report
    if args.report:
        os.makedirs(os.path.dirname(args.report), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(md_report)
        print(f"\n[OK] Markdown report saved to: {args.report}")


if __name__ == "__main__":
    main()
