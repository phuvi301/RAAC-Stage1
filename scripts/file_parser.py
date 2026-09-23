"""
Module: file_parser.py
Phân tích danh sách file thay đổi từ GitHub PR Files API:
- Nhận diện test files vs source files vs doc files.
- Đếm additions, deletions, status (modified, added, removed).
- Hỗ trợ đánh giá trục Testability (T) và Architecture Impact (I).
"""

import os
from typing import List, Dict, Any, Tuple


class FileParser:
    TEST_INDICATORS = [
        "/tests/", "/test/", "/testing/",
        "test_", "_test.", ".test.",
        "tests.", "spec.", "_spec."
    ]

    DOC_EXTENSIONS = [
        ".md", ".rst", ".txt", ".adoc", ".pdf",
        "doc/", "docs/", "documentation/", "license", "changelog"
    ]

    SOURCE_EXTENSIONS = [
        ".py", ".ts", ".js", ".java", ".go", ".rs", ".c", ".cpp",
        ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt"
    ]

    CONFIG_EXTENSIONS = [
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        "dockerfile", "makefile", ".lock"
    ]

    @classmethod
    def is_test_file(cls, filename: str) -> bool:
        """Kiểm tra đường dẫn file có thuộc test suite không."""
        fname_lower = filename.lower()
        return any(ind in fname_lower for ind in cls.TEST_INDICATORS)

    @classmethod
    def is_doc_file(cls, filename: str) -> bool:
        """Kiểm tra file có phải tài liệu thuần túy không."""
        fname_lower = filename.lower()
        return any(fname_lower.endswith(ext) or ext in fname_lower for ext in cls.DOC_EXTENSIONS)

    @classmethod
    def is_source_file(cls, filename: str) -> bool:
        """Kiểm tra file có phải mã nguồn thực thi chính không."""
        if cls.is_test_file(filename) or cls.is_doc_file(filename):
            return False
        fname_lower = filename.lower()
        return any(fname_lower.endswith(ext) for ext in cls.SOURCE_EXTENSIONS)

    @classmethod
    def is_comment_or_doc_patch(cls, patch_snippet: str) -> bool:
        """
        Kiểm tra xem toàn bộ các dòng thay đổi (+ hoặc -) trong patch có phải
        chỉ là comment, docstring, doc tags hoặc dòng trống hay không.
        """
        if not patch_snippet:
            return False

        changed_lines = []
        for line in patch_snippet.splitlines():
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            if line.startswith("+") or line.startswith("-"):
                changed_lines.append(line[1:].strip())

        if not changed_lines:
            return False

        doc_tag_prefixes = (
            ":param", ":type", ":return", ":rtype", ":raises", ":yield",
            "@param", "@return", "@returns", "@throws", "@exception", "@type", "@typedef",
            "@see", "@note", "@deprecated", "@override", "@author", "@brief", "@details",
            ".. note::", ".. warning::", ".. tip::", ".. important::"
        )

        for line in changed_lines:
            if not line:
                continue
            # Single line comment
            if line.startswith(("#", "//", "*", "/*", "*/", "rem ", "<!--")):
                continue
            # Docstring quotes
            if line.startswith(('"""', "'''")) or line.endswith(('"""', "'''")):
                continue
            # Sphinx / Javadoc / Doxygen style tags
            if any(line.startswith(prefix) for prefix in doc_tag_prefixes):
                continue
            # If any line has real code, then it's not comment/doc only
            return False

        return True

    @classmethod
    def extract_base_code(cls, patch: str, max_chars: int = 2000) -> str:
        """
        Trích xuất đoạn mã trước khi merge (base code) từ patch diff.
        Chỉ giữ lại các dòng ngữ cảnh (context lines) và dòng bị xóa/sửa (-),
        bỏ qua các dòng được thêm mới (+).
        """
        if not patch:
            return ""

        base_lines = []
        for line in patch.splitlines():
            # Bỏ qua hunk headers và file headers
            if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
                continue
            if line.startswith("\\ No newline at end of file"):
                continue
            # Dòng được thêm mới trong PR -> không tồn tại ở base code
            if line.startswith("+"):
                continue
            # Dòng bị xóa hoặc thay thế trong PR -> tồn tại ở base code
            if line.startswith("-"):
                base_lines.append(line[1:])
            # Dòng ngữ cảnh giữ nguyên
            elif line.startswith(" "):
                base_lines.append(line[1:])
            else:
                base_lines.append(line)

        result = "\n".join(base_lines).strip()
        if len(result) > max_chars:
            result = result[:max_chars] + "\n... [truncated base code] ..."
        return result

    @classmethod
    def parse_changed_files(cls, raw_files: List[Dict[str, Any]], base_commit: str = "", repo_full_name: str = "") -> Dict[str, Any]:
        """Phân loại và tổng hợp thống kê toàn bộ file thay đổi trong PR kèm base_code."""
        parsed_files = []
        test_files = []
        source_files = []
        doc_files = []
        substantive_source_files = []

        total_additions = 0
        total_deletions = 0

        for f in raw_files:
            filename = f.get("filename", "")
            additions = f.get("additions", 0)
            deletions = f.get("deletions", 0)
            status = f.get("status", "modified")
            patch = f.get("patch", "")

            total_additions += additions
            total_deletions += deletions

            is_test = cls.is_test_file(filename)
            is_doc = cls.is_doc_file(filename)
            is_src = cls.is_source_file(filename)
            patch_snippet = patch[:1500] if patch else ""
            is_comment_only = False

            if is_src and patch_snippet:
                is_comment_only = cls.is_comment_or_doc_patch(patch_snippet)

            # Trích xuất đoạn code trước khi merge (base_code)
            base_code = ""
            if status != "added" and patch:
                base_code = cls.extract_base_code(patch)

            base_file_url = ""
            if repo_full_name and base_commit:
                base_file_url = f"https://github.com/{repo_full_name}/blob/{base_commit}/{filename}"

            if is_test:
                test_files.append(filename)
            elif is_doc:
                doc_files.append(filename)
            elif is_src:
                source_files.append(filename)
                if not is_comment_only:
                    substantive_source_files.append(filename)

            parsed_files.append({
                "filename": filename,
                "status": status,
                "additions": additions,
                "deletions": deletions,
                "changes": f.get("changes", additions + deletions),
                "is_test": is_test,
                "is_source": is_src,
                "is_doc": is_doc,
                "is_comment_only": is_comment_only,
                # Lưu patch ngắn (tối đa 1500 chars mỗi file để tối ưu bộ nhớ)
                "patch_snippet": patch_snippet,
                # Đoạn code trước khi merge (base code) để AI so sánh và chấm điểm
                "base_code": base_code,
                "base_file_url": base_file_url
            })

        return {
            "total_files": len(parsed_files),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "files": parsed_files,
            "test_files_changed": len(test_files) > 0,
            "test_files_count": len(test_files),
            "test_file_list": test_files,
            "source_files_count": len(source_files),
            "source_file_list": source_files,
            "substantive_source_files_count": len(substantive_source_files),
            "substantive_source_file_list": substantive_source_files,
            "doc_only": (len(doc_files) == len(parsed_files)) if parsed_files else False
        }
