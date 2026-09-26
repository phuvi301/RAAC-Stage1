"""
Tests bắt buộc cho Repository Context Retrieval system.

Test 1 — Base commit respected: fetch_file dùng đúng base_commit, không phải HEAD.
Test 2 — Hallucinated path rejected: Retriever trả file không tồn tại → bị loại.
Test 3 — max_files enforced: Retriever trả > max_files → giới hạn đúng.
Test 4 — no PR leakage: Input gửi vào Context Retriever không chứa PR info.
Test 5 — issue_only mode: Pipeline cũ không gọi repository retrieval.
Test 6 — repo_aware mode: Pipeline mới hoạt động đúng đầu đủ.
Test 7 — retrieval failure: Fallback to issue-only khi retrieval fail.
"""

import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, call

# Đảm bảo import được từ project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ===========================================================================
# Test 1 — Base commit respected
# ===========================================================================

class TestBaseCommitRespected:
    """
    Đảm bảo fetch_file dùng đúng base_commit, KHÔNG fetch từ HEAD.
    """

    def test_get_file_content_uses_base_commit_not_head(self):
        """get_file_content phải gọi GitHub API với ref=base_commit, không phải HEAD."""
        from analyzer.repo_provider import get_file_content

        mock_client = MagicMock()
        # Giả lập phản hồi GitHub API cho file content
        mock_client.get.return_value = {
            "encoding": "base64",
            "content": "aGVsbG8gd29ybGQ=",  # "hello world" base64
            "size": 11,
        }

        base_commit = "abc1234567890abcdef"
        head_sha = "deadbeef00000000000"  # HEAD - không được dùng

        with patch("analyzer.repo_provider._get_github_client", return_value=mock_client):
            # Tắt cache để luôn gọi API
            with patch("analyzer.repo_provider.os.path.exists", return_value=False):
                result = get_file_content("psf/requests", "src/requests/models.py", base_commit)

        # Kiểm tra rằng ref được truyền vào là base_commit, KHÔNG phải HEAD
        call_args = mock_client.get.call_args
        params = call_args[1].get("params") or (call_args[0][1] if len(call_args[0]) > 1 else {})
        assert params.get("ref") == base_commit, (
            f"Expected ref={base_commit!r} but got ref={params.get('ref')!r}. "
            "HEAD should never be used when base_commit is available."
        )
        assert params.get("ref") != head_sha, "HEAD SHA leaked into file fetch!"
        assert result is not None

    def test_get_repo_tree_uses_base_commit(self):
        """get_repo_tree phải gọi endpoint với base_commit SHA, không phải 'main' hay 'HEAD'."""
        from analyzer.repo_provider import get_repo_tree

        mock_client = MagicMock()
        mock_client.get.return_value = {
            "tree": [
                {"type": "blob", "path": "src/requests/models.py"},
                {"type": "blob", "path": "tests/test_requests.py"},
            ]
        }

        base_commit = "0b401c76b6e80a4eecf3c690085b2553f6e261ca"

        with patch("analyzer.repo_provider._get_github_client", return_value=mock_client):
            with patch("analyzer.repo_provider.os.path.exists", return_value=False):
                with patch("builtins.open", MagicMock()):
                    with patch("json.dump"):
                        result = get_repo_tree("psf/requests", base_commit, use_cache=False)

        # Kiểm tra endpoint chứa base_commit SHA
        call_args = mock_client.get.call_args
        endpoint = call_args[0][0]
        assert base_commit in endpoint, (
            f"Endpoint '{endpoint}' không chứa base_commit SHA '{base_commit}'. "
            "Tree phải được lấy tại đúng base_commit."
        )
        assert "HEAD" not in endpoint
        assert "main" not in endpoint
        assert "master" not in endpoint


# ===========================================================================
# Test 2 — Hallucinated path rejected
# ===========================================================================

class TestHallucinatedPathRejected:
    """Retriever trả file không tồn tại trong tree → bị loại."""

    def test_hallucinated_paths_are_rejected(self):
        """Paths không có trong repository_tree phải bị reject."""
        from analyzer.context_retriever import _validate_selected_files

        repository_tree = [
            "src/requests/models.py",
            "src/requests/sessions.py",
            "tests/test_requests.py",
        ]

        raw_files = [
            {"path": "src/requests/models.py", "reason": "Mentioned in issue."},
            {"path": "made_up_file_that_does_not_exist.py", "reason": "Hallucinated path."},
            {"path": "another/fake/path.py", "reason": "Another hallucination."},
        ]

        validated = _validate_selected_files(raw_files, repository_tree, max_files=5)

        paths = [f["path"] for f in validated]
        assert "src/requests/models.py" in paths, "Valid path should be kept"
        assert "made_up_file_that_does_not_exist.py" not in paths, "Hallucinated path should be rejected"
        assert "another/fake/path.py" not in paths, "Hallucinated path should be rejected"
        assert len(validated) == 1

    def test_all_hallucinated_returns_empty(self):
        """Nếu tất cả đều là hallucinated → trả về []."""
        from analyzer.context_retriever import _validate_selected_files

        repository_tree = ["src/real/file.py"]
        raw_files = [
            {"path": "nonexistent1.py", "reason": "Fake 1"},
            {"path": "nonexistent2.py", "reason": "Fake 2"},
        ]
        validated = _validate_selected_files(raw_files, repository_tree, max_files=5)
        assert validated == [], "All hallucinated paths should return empty list"


# ===========================================================================
# Test 3 — max_files enforced
# ===========================================================================

class TestMaxFilesEnforced:
    """Retriever trả > max_files → giới hạn đúng max_files."""

    def test_max_files_limit_respected(self):
        """Chỉ lấy tối đa max_files file, dù LLM trả nhiều hơn."""
        from analyzer.context_retriever import _validate_selected_files

        # 10 files đều valid trong tree
        repository_tree = [f"src/module_{i}.py" for i in range(10)]
        raw_files = [
            {"path": f"src/module_{i}.py", "reason": f"Reason {i}"}
            for i in range(10)
        ]

        max_files = 3
        validated = _validate_selected_files(raw_files, repository_tree, max_files=max_files)

        assert len(validated) == max_files, (
            f"Expected max {max_files} files but got {len(validated)}. "
            "max_files must be enforced even when LLM returns more."
        )

    def test_max_files_when_fewer_available(self):
        """Nếu LLM trả ít hơn max_files → giữ tất cả."""
        from analyzer.context_retriever import _validate_selected_files

        repository_tree = ["src/a.py", "src/b.py"]
        raw_files = [
            {"path": "src/a.py", "reason": "Relevant"},
        ]
        validated = _validate_selected_files(raw_files, repository_tree, max_files=5)
        assert len(validated) == 1


# ===========================================================================
# Test 4 — no PR leakage
# ===========================================================================

class TestNoPRLeakage:
    """Input gửi vào Context Retriever KHÔNG chứa bất kỳ thông tin PR nào."""

    def test_retriever_prompt_no_pr_info(self):
        """User prompt cho retriever không được chứa PR URL, PR number, changed_files, patch, head SHA."""
        from analyzer.context_retriever import _build_retriever_user_prompt

        repo = "psf/requests"
        base_commit = "0b401c76b6e80a4eecf3c690085b2553f6e261ca"
        head_sha = "deadbeef99999999999999999999999999999999"  # HEAD - không được xuất hiện
        pr_number = "7433"
        pr_url = "https://github.com/psf/requests/pull/7433"
        changed_files_hint = "changed_files"

        issue_title = "`prepare_body` stream detection regression"
        issue_body = "When calling session.post(...) with a stream, the body is incorrectly detected."

        user_prompt = _build_retriever_user_prompt(
            repo=repo,
            base_commit=base_commit,
            issue_title=issue_title,
            issue_body=issue_body,
            repository_tree=["src/requests/models.py", "tests/test_requests.py"],
        )

        # Không được chứa thông tin PR
        assert pr_url not in user_prompt, f"PR URL leaked into retriever prompt!"
        assert head_sha not in user_prompt, f"HEAD SHA leaked into retriever prompt!"
        assert f"pull/{pr_number}" not in user_prompt, f"PR number leaked into retriever prompt!"
        assert "changed_files" not in user_prompt.lower(), f"changed_files leaked into retriever prompt!"
        assert "patch" not in user_prompt.lower() or "dispatch" in user_prompt.lower(), (
            "Word 'patch' should not appear in retriever prompt unless it's part of issue content"
        )
        # Phải chứa base_commit
        assert base_commit in user_prompt, "base_commit should be in retriever prompt for reproducibility"

    def test_retriever_receives_only_issue_and_tree(self):
        """
        RepositoryContextRetriever.retrieve() chỉ được nhận issue title, body, tree, repo, base_commit.
        Không nhận PR URL, changed_files, patch, head SHA.
        """
        from analyzer.context_retriever import RepositoryContextRetriever

        mock_llm = MagicMock()
        mock_llm.generate.return_value = {
            "raw_text": json.dumps({"files": [{"path": "src/requests/models.py", "reason": "Test"}]}),
            "model": "mock",
        }

        retriever = RepositoryContextRetriever(llm_client=mock_llm, max_files=5)

        pr_info_record = {
            "id": "psf__requests-1766",
            "repo": "psf/requests",
            "base_commit": "abc123",
            "title": "Some issue title",
            "body": "Issue body text",
            # Các field PR này KHÔNG được truyền vào retriever
            "pr_url": "https://github.com/psf/requests/pull/1766",
            "pr_number": 1766,
            "changed_files": ["src/requests/models.py"],
            "patch": "--- a/src/requests/models.py\n+++ b/src/requests/models.py\n...",
        }

        result = retriever.retrieve(
            repo=pr_info_record["repo"],
            base_commit=pr_info_record["base_commit"],
            issue_title=pr_info_record["title"],
            issue_body=pr_info_record["body"],
            repository_tree=["src/requests/models.py", "tests/test_requests.py"],
            issue_id=pr_info_record["id"],
        )

        # Kiểm tra prompt gửi tới LLM không chứa PR info
        generate_call = mock_llm.generate.call_args
        user_prompt = generate_call[0][1]  # second positional arg

        assert "pull/1766" not in user_prompt, "PR URL in retriever user prompt — leakage!"
        assert pr_info_record["patch"][:50] not in user_prompt, "Patch content in retriever prompt — leakage!"
        assert "changed_files" not in user_prompt.lower(), "changed_files in retriever prompt — leakage!"


# ===========================================================================
# Test 5 — issue_only mode
# ===========================================================================

class TestIssueOnlyMode:
    """Pipeline cũ (issue_only) vẫn hoạt động mà không gọi repository retrieval."""

    def test_issue_only_does_not_call_repo_retrieval(self):
        """Khi mode=issue_only, không có bất kỳ lời gọi get_repo_tree nào."""
        from analyzer.batch_runner import BatchRunner
        from analyzer.llm_client import MockLLMClient

        runner = BatchRunner(
            llm_client=MockLLMClient(),
            prompt_version="v3",
            output_dir="data/analyzer_outputs",
            mode="issue_only",
        )

        assert runner.mode == "issue_only"
        assert runner._retriever is None, "Retriever should not be initialized in issue_only mode"
        assert runner._context_builder is None, "ContextBuilder should not be initialized in issue_only mode"

    def test_issue_only_prompt_has_no_repo_context(self):
        """Prompt của issue_only mode không chứa # REPOSITORY CONTEXT section."""
        from analyzer.prompt_builder import PromptBuilder

        builder = PromptBuilder(prompt_version="v3")
        issue_record = {
            "id": "test-issue-001",
            "repo": "psf/requests",
            "title": "Test issue",
            "body": "Test body",
            "base_commit": "abc123",
        }

        _, user_prompt = builder.build_prompts(issue_record, repo_context_text=None)
        assert "# REPOSITORY CONTEXT" not in user_prompt, (
            "issue_only mode should not inject REPOSITORY CONTEXT into prompt"
        )

    def test_issue_only_batch_result_has_skipped_status(self):
        """Kết quả issue_only phải có retrieval.repository_context_status = 'skipped'."""
        from analyzer.batch_runner import BatchRunner
        from analyzer.llm_client import MockLLMClient

        runner = BatchRunner(
            llm_client=MockLLMClient(),
            prompt_version="v3",
            output_dir="data/analyzer_outputs",
            mode="issue_only",
        )

        issue_record = {
            "id": "test-issue-001",
            "repo": "psf/requests",
            "title": "Test issue",
            "body": "Test body",
        }

        result = runner.process_issue(issue_record)
        retrieval_meta = result.get("metadata", {}).get("retrieval", {})
        assert retrieval_meta.get("repository_context_status") == "skipped", (
            f"issue_only mode should have retrieval status='skipped', "
            f"got: {retrieval_meta.get('repository_context_status')!r}"
        )


# ===========================================================================
# Test 6 — repo_aware mode
# ===========================================================================

class TestRepoAwareMode:
    """Pipeline repo_aware hoạt động đúng: issue → tree → retriever → files → analyzer."""

    def test_repo_aware_full_pipeline(self):
        """
        Pipeline: Issue → tree → LLM retriever → context → Analyzer.
        Dùng mock ở mọi bước để kiểm tra luồng gọi.
        """
        from analyzer.batch_runner import BatchRunner
        from analyzer.llm_client import MockLLMClient

        # LLM mock cho cả retriever lẫn analyzer
        mock_llm = MagicMock()
        # Call 1: retriever (trả JSON với files)
        # Call 2: analyzer (trả JSON rubric)
        sample_profile = json.dumps({
            "complexity": {"score": 3, "evidence": "Multiple components affected across the codebase"},
            "testability": {"score": 3, "evidence": "Testable with unit tests using mock fixtures"},
            "security_sensitivity": {"score": 1, "evidence": "No sensitive data or auth flows involved"},
            "architecture_impact": {"score": 2, "evidence": "Moderate impact on existing architecture"},
        })
        mock_llm.generate.side_effect = [
            # Retriever call
            {
                "raw_text": json.dumps({
                    "files": [{"path": "src/requests/models.py", "reason": "Core models"}]
                }),
                "model": "mock-retriever",
            },
            # Analyzer call
            {
                "raw_text": sample_profile,
                "model": "mock-analyzer",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "latency_ms": 100,
            }
        ]

        fake_tree = ["src/requests/models.py", "tests/test_requests.py"]
        fake_content = "class PreparedRequest:\n    def prepare_body(self):\n        pass\n"

        issue_record = {
            "id": "psf__requests-1766",
            "repo": "psf/requests",
            "title": "prepare_body regression",
            "body": "PreparedRequest.prepare_body fails on streams.",
            "base_commit": "abc1234567890",
        }

        with patch("analyzer.repo_provider.get_repo_tree", return_value=fake_tree) as mock_tree:
            with patch("analyzer.context_builder.get_file_content", return_value=fake_content):
                runner = BatchRunner(
                    llm_client=mock_llm,
                    prompt_version="v3",
                    output_dir="data/analyzer_outputs",
                    mode="repo_aware",
                    retriever_max_files=5,
                )
                result = runner.process_issue(issue_record, max_retries=1)

        # Kiểm tra tree được gọi đúng
        mock_tree.assert_called_once_with("psf/requests", "abc1234567890")

        # Kiểm tra kết quả
        assert result.get("profile") is not None, "Profile should be generated"
        retrieval_meta = result.get("metadata", {}).get("retrieval", {})
        assert retrieval_meta.get("mode") == "repo_aware"
        assert retrieval_meta.get("repository_context_status") == "success"
        assert len(retrieval_meta.get("retrieved_files", [])) >= 1

    def test_repo_aware_prompt_contains_context_section(self):
        """User prompt trong repo_aware mode phải chứa # REPOSITORY CONTEXT."""
        from analyzer.prompt_builder import PromptBuilder

        builder = PromptBuilder(prompt_version="v3")
        issue_record = {
            "id": "test-001",
            "repo": "psf/requests",
            "title": "Test issue",
            "body": "Test body",
        }
        context_text = "# REPOSITORY CONTEXT\n\nRepository: psf/requests\nRevision: abc123\n\n..."

        _, user_prompt = builder.build_prompts(issue_record, repo_context_text=context_text)

        assert "# REPOSITORY CONTEXT" in user_prompt, (
            "repo_aware mode must inject REPOSITORY CONTEXT section into user prompt"
        )
        assert "psf/requests" in user_prompt


# ===========================================================================
# Test 7 — retrieval failure → fallback issue-only
# ===========================================================================

class TestRetrievalFailureFallback:
    """Khi GitHub/API/retriever fail → fallback về issue-only và log rõ trạng thái."""

    def test_empty_tree_fallback(self):
        """Nếu get_repo_tree trả [] → fallback_issue_only."""
        from analyzer.batch_runner import BatchRunner
        from analyzer.llm_client import MockLLMClient

        mock_llm = MockLLMClient()
        issue_record = {
            "id": "test-fail-001",
            "repo": "psf/requests",
            "title": "Test issue",
            "body": "Test body",
            "base_commit": "abc123",
        }

        with patch("analyzer.repo_provider.get_repo_tree", return_value=[]):
            runner = BatchRunner(
                llm_client=mock_llm,
                prompt_version="v3",
                output_dir="data/analyzer_outputs",
                mode="repo_aware",
            )
            result = runner.process_issue(issue_record)

        retrieval_meta = result.get("metadata", {}).get("retrieval", {})
        assert retrieval_meta.get("repository_context_status") == "fallback_issue_only", (
            "Empty tree should trigger fallback_issue_only"
        )
        assert retrieval_meta.get("fallback_reason") == "empty_tree"
        # Pipeline không crash, vẫn trả về profile
        assert result.get("profile") is not None, "Should still produce profile via issue-only fallback"

    def test_github_api_error_fallback(self):
        """Nếu GitHub API raise exception → fallback_issue_only, không crash batch."""
        from analyzer.batch_runner import BatchRunner
        from analyzer.llm_client import MockLLMClient

        mock_llm = MockLLMClient()
        issue_record = {
            "id": "test-fail-002",
            "repo": "psf/requests",
            "title": "Test issue",
            "body": "Test body",
            "base_commit": "abc123",
        }

        with patch("analyzer.repo_provider.get_repo_tree", side_effect=Exception("GitHub API timeout")):
            runner = BatchRunner(
                llm_client=mock_llm,
                prompt_version="v3",
                output_dir="data/analyzer_outputs",
                mode="repo_aware",
            )
            result = runner.process_issue(issue_record)

        retrieval_meta = result.get("metadata", {}).get("retrieval", {})
        assert retrieval_meta.get("repository_context_status") == "fallback_issue_only"
        assert "timeout" in str(retrieval_meta.get("fallback_reason", "")).lower()
        assert result.get("profile") is not None, "Should still produce profile via issue-only fallback"

    def test_missing_base_commit_fallback(self):
        """Nếu issue record không có base_commit → fallback_issue_only."""
        from analyzer.batch_runner import BatchRunner
        from analyzer.llm_client import MockLLMClient

        mock_llm = MockLLMClient()
        issue_record = {
            "id": "test-fail-003",
            "repo": "psf/requests",
            "title": "Test issue",
            "body": "Test body",
            # base_commit bị thiếu
        }

        runner = BatchRunner(
            llm_client=mock_llm,
            prompt_version="v3",
            output_dir="data/analyzer_outputs",
            mode="repo_aware",
        )
        result = runner.process_issue(issue_record)

        retrieval_meta = result.get("metadata", {}).get("retrieval", {})
        assert retrieval_meta.get("repository_context_status") == "fallback_issue_only"
        assert result.get("profile") is not None, "Should still produce profile via issue-only fallback"

    def test_retriever_llm_error_fallback(self):
        """Nếu LLM retriever call thất bại → fallback_issue_only, analyzer vẫn chạy."""
        from analyzer.batch_runner import BatchRunner
        from analyzer.llm_client import MockLLMClient

        # LLM: retriever gọi đầu tiên sẽ fail, analyzer gọi thứ hai sẽ thành công
        mock_llm = MagicMock()
        sample_profile = json.dumps({
            "complexity": {"score": 2, "evidence": "Simple isolated change in one module"},
            "testability": {"score": 2, "evidence": "Easy to test with standard unit tests"},
            "security_sensitivity": {"score": 1, "evidence": "No security implications identified"},
            "architecture_impact": {"score": 1, "evidence": "Internal implementation change only"},
        })
        # Retriever gọi generate → raise exception
        # Analyzer gọi generate → thành công
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("LLM retriever timeout")
            return {
                "raw_text": sample_profile,
                "model": "mock",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "latency_ms": 100,
            }
        mock_llm.generate.side_effect = side_effect

        issue_record = {
            "id": "test-fail-004",
            "repo": "psf/requests",
            "title": "Test issue",
            "body": "Test body",
            "base_commit": "abc123",
        }

        fake_tree = ["src/requests/models.py"]

        with patch("analyzer.repo_provider.get_repo_tree", return_value=fake_tree):
            runner = BatchRunner(
                llm_client=mock_llm,
                prompt_version="v3",
                output_dir="data/analyzer_outputs",
                mode="repo_aware",
            )
            result = runner.process_issue(issue_record, max_retries=1)

        retrieval_meta = result.get("metadata", {}).get("retrieval", {})
        assert retrieval_meta.get("repository_context_status") == "fallback_issue_only"
        assert result.get("profile") is not None, "Should still produce profile via issue-only fallback"


# ===========================================================================
# Bonus: Integration test helpers (không cần GitHub API thật)
# ===========================================================================

class TestContextRetrieverValidation:
    """Additional validation tests cho ContextRetriever."""

    def test_duplicates_removed(self):
        """Duplicate paths trong output LLM phải bị loại bỏ."""
        from analyzer.context_retriever import _validate_selected_files

        tree = ["src/a.py", "src/b.py"]
        raw_files = [
            {"path": "src/a.py", "reason": "First mention"},
            {"path": "src/a.py", "reason": "Duplicate mention"},
            {"path": "src/b.py", "reason": "Another file"},
        ]

        validated = _validate_selected_files(raw_files, tree, max_files=10)
        paths = [f["path"] for f in validated]

        assert paths.count("src/a.py") == 1, "Duplicate path should be removed"
        assert "src/b.py" in paths

    def test_tree_filtering_excludes_binary(self):
        """get_repo_tree phải loại bỏ binary files và junk paths."""
        from analyzer.repo_provider import _is_excluded

        # Nên bị loại
        assert _is_excluded("image.png"), "PNG files should be excluded"
        assert _is_excluded("docs/image.jpg"), "JPEG files should be excluded"
        assert _is_excluded("dist/bundle.zip"), "ZIP files should be excluded"
        assert _is_excluded("__pycache__/module.cpython-312.pyc"), "__pycache__ should be excluded"
        assert _is_excluded("node_modules/package/index.js"), "node_modules should be excluded"

        # Không nên bị loại
        assert not _is_excluded("src/requests/models.py"), "Python source files should be kept"
        assert not _is_excluded("tests/test_requests.py"), "Test files should be kept"
        assert not _is_excluded("setup.py"), "Setup files should be kept"
        assert not _is_excluded("README.md"), "Markdown docs should be kept"
        assert not _is_excluded("pyproject.toml"), "Config files should be kept"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
