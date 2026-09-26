"""
Module: analyzer/context_builder.py
Xây dựng phần # REPOSITORY CONTEXT trong final Requirement Analyzer prompt.

Chức năng:
  - Nhận danh sách selected_files (path + reason) từ ContextRetriever
  - Fetch nội dung từng file @ base_commit qua repo_provider (có cache)
  - Tôn trọng token budget: max_chars_per_file và max_total_chars
  - Với file lớn: trích snippet quanh các identifier xuất hiện trong issue
  - Tách source code files và test files thành hai section riêng
  - Trả về formatted context string + metadata
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from analyzer.repo_provider import get_file_content

logger = logging.getLogger("ContextBuilder")

# Default token budget (configurable)
DEFAULT_MAX_CHARS_PER_FILE = 12_000
DEFAULT_MAX_TOTAL_CHARS = 40_000
DEFAULT_SNIPPET_CONTEXT_LINES = 30  # số dòng trước/sau identifier khi cắt snippet


# ---------------------------------------------------------------------------
# Identifier extraction from issue
# ---------------------------------------------------------------------------

def _extract_identifiers(title: str, body: str) -> List[str]:
    """
    Trích xuất các identifier Python/code từ issue title và body.
    Ưu tiên: snake_case, CamelCase, backtick-wrapped names, function calls.
    """
    text = f"{title}\n{body}"
    identifiers = set()

    # Từ backtick (e.g. `prepare_body`, `PreparedRequest`)
    for m in re.finditer(r'`([A-Za-z_][A-Za-z0-9_.]+)`', text):
        identifiers.add(m.group(1).strip("."))

    # CamelCase words (>= 4 chars, starts uppercase)
    for m in re.finditer(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text):
        identifiers.add(m.group(1))

    # snake_case words có dấu gạch dưới (>= 2 parts)
    for m in re.finditer(r'\b([a-z][a-z0-9]+(?:_[a-z0-9]+)+)\b', text):
        word = m.group(1)
        if len(word) >= 5:  # bỏ qua từ quá ngắn như "is_ok"
            identifiers.add(word)

    # Loại bỏ các từ thông thường không phải identifier code
    common_words = {
        "should", "would", "could", "might", "when", "that", "this", "with",
        "from", "have", "been", "will", "they", "than", "then", "also",
        "some", "such", "into", "more", "over", "after", "before", "being",
        "their", "there", "these", "those", "which", "while", "about",
    }
    identifiers -= common_words

    return sorted(identifiers, key=len, reverse=True)  # dài trước (ưu tiên cụ thể hơn)


# ---------------------------------------------------------------------------
# Snippet extraction from large files
# ---------------------------------------------------------------------------

def _find_relevant_lines(
    content: str,
    identifiers: List[str],
    context_lines: int = DEFAULT_SNIPPET_CONTEXT_LINES,
) -> Tuple[int, int]:
    """
    Tìm vùng dòng quan trọng nhất trong file dựa trên identifiers.
    Returns (start_line_1indexed, end_line_1indexed).
    """
    lines = content.splitlines()
    if not lines:
        return 1, 1

    # Tính điểm cho từng dòng
    scores = [0] * len(lines)
    for i, line in enumerate(lines):
        for ident in identifiers:
            if ident in line:
                # Điểm cao hơn cho định nghĩa (def, class) vs usage
                if re.search(rf'\b(def|class)\s+{re.escape(ident)}\b', line):
                    scores[i] += 10
                else:
                    scores[i] += 2

    if max(scores) == 0:
        # Không tìm thấy identifier nào, trả về phần đầu file
        end = min(context_lines * 2, len(lines))
        return 1, end

    # Tìm điểm tập trung cao nhất
    best_center = max(range(len(scores)), key=lambda i: scores[i])

    start = max(0, best_center - context_lines)
    end = min(len(lines) - 1, best_center + context_lines)

    return start + 1, end + 1  # 1-indexed


def _extract_snippet(
    content: str,
    identifiers: List[str],
    max_chars: int,
    context_lines: int = DEFAULT_SNIPPET_CONTEXT_LINES,
) -> Tuple[str, int, int]:
    """
    Trích snippet từ content, tôn trọng max_chars.
    Returns (snippet_text, start_line, end_line) — 1-indexed.
    """
    lines = content.splitlines()

    if not content.strip():
        return "", 1, 1

    # Nếu file đủ nhỏ, trả về toàn bộ
    if len(content) <= max_chars:
        return content, 1, len(lines)

    # Tìm vùng quan trọng nhất
    start_line, end_line = _find_relevant_lines(content, identifiers, context_lines)

    # Cắt đoạn
    snippet_lines = lines[start_line - 1 : end_line]
    snippet = "\n".join(snippet_lines)

    # Nếu vẫn còn quá dài, cắt bớt từ cuối
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars] + "\n... [truncated for token budget] ..."

    return snippet, start_line, end_line


# ---------------------------------------------------------------------------
# Detect language
# ---------------------------------------------------------------------------

def _detect_language(path: str) -> str:
    """Detect ngôn ngữ lập trình từ extension để format code block."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    lang_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "java": "java", "go": "go", "rs": "rust",
        "c": "c", "cpp": "cpp", "h": "c", "hpp": "cpp",
        "rb": "ruby", "php": "php", "cs": "csharp",
        "md": "markdown", "rst": "rst",
        "yml": "yaml", "yaml": "yaml",
        "toml": "toml", "cfg": "ini", "ini": "ini",
        "sh": "bash", "bat": "batch",
        "json": "json", "xml": "xml", "html": "html",
        "txt": "text",
    }
    return lang_map.get(ext, ext or "text")


def _is_test_file(path: str) -> bool:
    """Kiểm tra xem file có phải test file không."""
    lower = path.lower()
    return (
        "/test" in lower or "\\test" in lower
        or lower.startswith("test")
        or "_test." in lower
        or "test_" in lower.split("/")[-1]
        or "spec" in lower
    )


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

class ContextBuilder:
    """
    Lấy nội dung các file đã được ContextRetriever chọn, build phần
    '# REPOSITORY CONTEXT' cho final Requirement Analyzer prompt.
    """

    def __init__(
        self,
        max_chars_per_file: int = DEFAULT_MAX_CHARS_PER_FILE,
        max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    ):
        self.max_chars_per_file = max_chars_per_file
        self.max_total_chars = max_total_chars

    def build(
        self,
        repo: str,
        base_commit: str,
        issue_title: str,
        issue_body: str,
        selected_files: List[Dict[str, Any]],
        repository_tree: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build repository context section.

        Returns:
        {
            "context_text": "# REPOSITORY CONTEXT\n...",
            "file_snippets": [{"path": ..., "start_line": ..., "end_line": ..., "content": ..., "is_test": ...}],
            "tree_summary": "...",
            "total_chars": 123,
            "files_included": 3,
            "files_skipped": [...],
        }
        """
        identifiers = _extract_identifiers(issue_title, issue_body)
        logger.info(f"[ContextBuilder] Identifiers extracted: {identifiers[:10]}")

        file_snippets = []
        files_skipped = []
        total_chars = 0

        for sel in selected_files:
            path = sel.get("path", "")
            if not path:
                continue

            if total_chars >= self.max_total_chars:
                files_skipped.append({"path": path, "reason": "total_budget_exceeded"})
                logger.info(f"[ContextBuilder] Skipping {path}: total budget exceeded")
                continue

            content = get_file_content(repo, path, base_commit)
            if content is None:
                files_skipped.append({"path": path, "reason": "fetch_failed"})
                logger.warning(f"[ContextBuilder] Could not fetch {path}@{base_commit[:8]}")
                continue

            if not content.strip():
                files_skipped.append({"path": path, "reason": "empty_file"})
                continue

            remaining_budget = self.max_total_chars - total_chars
            effective_max = min(self.max_chars_per_file, remaining_budget)

            snippet, start_line, end_line = _extract_snippet(content, identifiers, effective_max)

            if not snippet.strip():
                files_skipped.append({"path": path, "reason": "empty_snippet"})
                continue

            total_chars += len(snippet)
            file_snippets.append({
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
                "content": snippet,
                "language": _detect_language(path),
                "is_test": _is_test_file(path),
                "reason": sel.get("reason", ""),
            })

        # Build tree summary (top-level directories + counts)
        tree_summary = self._build_tree_summary(repository_tree or [])

        # Format context string
        context_text = self._format_context(repo, base_commit, tree_summary, file_snippets)

        return {
            "context_text": context_text,
            "file_snippets": file_snippets,
            "tree_summary": tree_summary,
            "total_chars": total_chars,
            "files_included": len(file_snippets),
            "files_skipped": files_skipped,
        }

    def _build_tree_summary(self, repository_tree: List[str]) -> str:
        """
        Tạo tóm tắt cấu trúc thư mục cấp cao nhất từ repository tree.
        """
        if not repository_tree:
            return "(repository tree not available)"

        # Đếm files theo top-level directory
        dir_counts: Dict[str, int] = {}
        for path in repository_tree:
            parts = path.split("/")
            if len(parts) > 1:
                top = parts[0]
            else:
                top = "(root)"
            dir_counts[top] = dir_counts.get(top, 0) + 1

        # Sắp xếp theo count giảm dần
        sorted_dirs = sorted(dir_counts.items(), key=lambda x: -x[1])

        lines = []
        for d, count in sorted_dirs[:20]:  # top 20 dirs
            lines.append(f"  {d}/  ({count} files)")

        summary = "\n".join(lines)
        if len(dir_counts) > 20:
            summary += f"\n  ... and {len(dir_counts) - 20} more directories"

        return summary

    def _format_context(
        self,
        repo: str,
        base_commit: str,
        tree_summary: str,
        file_snippets: List[Dict[str, Any]],
    ) -> str:
        """
        Format phần # REPOSITORY CONTEXT theo spec (Section 11 của temp_prompt.md).
        Tuân thủ: không nói 'changed by PR', chỉ nói 'may be relevant to understanding the issue'.
        """
        parts = []
        parts.append("# REPOSITORY CONTEXT")
        parts.append("")
        parts.append(f"Repository: {repo}")
        parts.append(f"Revision: {base_commit}")
        parts.append("")
        parts.append(
            "The following repository context comes from the codebase BEFORE the issue's\n"
            "solution was applied.\n"
            "\n"
            "Use it only to understand the scope, structure, dependencies, current behavior,\n"
            "and testability of the requirement.\n"
            "\n"
            "Do not assume that these files are necessarily the files that should be modified.\n"
            "\n"
            "These files were retrieved because they may be relevant to understanding the issue."
        )
        parts.append("")
        parts.append("## Repository Structure")
        parts.append("")
        parts.append(tree_summary)
        parts.append("")

        source_snippets = [s for s in file_snippets if not s["is_test"]]
        test_snippets = [s for s in file_snippets if s["is_test"]]

        if source_snippets:
            parts.append("## Relevant Pre-Fix Source Code")
            parts.append("")
            for s in source_snippets:
                parts.append(f"### {s['path']}")
                parts.append("")
                parts.append(f"Lines {s['start_line']}-{s['end_line']}")
                parts.append("")
                parts.append(f"```{s['language']}")
                parts.append(s["content"])
                parts.append("```")
                parts.append("")

        if test_snippets:
            parts.append("## Existing Pre-Fix Tests")
            parts.append("")
            for s in test_snippets:
                parts.append(f"### {s['path']}")
                parts.append("")
                parts.append(f"Lines {s['start_line']}-{s['end_line']}")
                parts.append("")
                parts.append(f"```{s['language']}")
                parts.append(s["content"])
                parts.append("```")
                parts.append("")

        return "\n".join(parts)
