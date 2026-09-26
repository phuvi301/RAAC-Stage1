"""
Module: batch_runner.py
Điều phối chạy batch Requirement Analyzer cho toàn bộ benchmark dataset:
- Quản lý checkpoint (lưu tiến độ từng issue, tự động resume khi chạy lại).
- Tự động retry khi gặp lỗi mạng/rate-limit.
- Kiểm tra tính hợp lệ qua ProfileValidator.
- Xuất kết quả chuẩn hóa vào data/analyzer_outputs/.
- Hỗ trợ hai mode: issue_only (behavior gốc) và repo_aware (Repository Context Retrieval).
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer.llm_client import get_llm_client, BaseLLMClient
from analyzer.prompt_builder import PromptBuilder
from analyzer.output_parser import OutputParser
from analyzer.validator import ProfileValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BatchRunner")


class BatchRunner:
    def __init__(
        self,
        llm_client: BaseLLMClient,
        prompt_version: str = "v3",
        output_dir: str = "data/analyzer_outputs",
        checkpoint_path: Optional[str] = None,
        temperature: Optional[float] = None,
        run_label: Optional[str] = None,
        include_base_code: bool = False,
        verbose: bool = True,
        mode: str = "issue_only",          # "issue_only" hoặc "repo_aware"
        retriever_max_files: int = 5,       # số file tối đa retriever chọn
        context_max_chars_per_file: int = 12_000,
        context_max_total_chars: int = 40_000,
    ):
        self.client = llm_client
        self.prompt_version = prompt_version
        self.output_dir = output_dir
        self.run_label = run_label
        self.include_base_code = include_base_code
        self.verbose = verbose
        self.mode = mode
        self.retriever_max_files = retriever_max_files
        self.raw_lookup: Dict[str, Any] = {}
        os.makedirs(self.output_dir, exist_ok=True)

        # Thiết lập lưu log chi tiết vào thư mục data/analyzer_outputs/logs
        log_dir = os.path.join(self.output_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        label_part = f"_{run_label}" if run_label else ""
        mode_part = f"_{mode}" if mode != "issue_only" else ""
        self.log_file = os.path.join(log_dir, f"analyzer_{prompt_version}{label_part}{mode_part}_{timestamp_str}.log")

        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(file_handler)
        logger.info(f"Execution log will be saved to: {self.log_file}")
        logger.info(f"Pipeline mode: {self.mode}")

        if self.include_base_code:
            self._load_raw_lookup()

        # Khởi tạo retriever và context builder nếu chạy repo_aware mode
        self._retriever = None
        self._context_builder = None
        if self.mode == "repo_aware":
            self._init_repo_aware_components(context_max_chars_per_file, context_max_total_chars)

        if checkpoint_path:
            self.checkpoint_path = checkpoint_path
        else:
            default_cp = os.path.join(self.output_dir, f"checkpoint_{prompt_version}{label_part}{mode_part}.json")
            # Tương thích ngược: nếu chạy v2 không nhãn mà checkpoint.json cũ tồn tại
            legacy_cp = os.path.join(self.output_dir, "checkpoint.json")
            if prompt_version == "v2" and not run_label and not os.path.exists(default_cp) and os.path.exists(legacy_cp):
                self.checkpoint_path = legacy_cp
            else:
                self.checkpoint_path = default_cp

        self.temperature = temperature if temperature is not None else (0.0 if prompt_version.lower().startswith("v3") else 0.1)
        self.builder = PromptBuilder(prompt_version=prompt_version)

    def _init_repo_aware_components(self, max_chars_per_file: int, max_total_chars: int):
        """Khởi tạo RepositoryContextRetriever và ContextBuilder cho repo_aware mode."""
        try:
            from analyzer.context_retriever import RepositoryContextRetriever
            from analyzer.context_builder import ContextBuilder
            self._retriever = RepositoryContextRetriever(
                llm_client=self.client,
                max_files=self.retriever_max_files,
                temperature=0.0,
            )
            self._context_builder = ContextBuilder(
                max_chars_per_file=max_chars_per_file,
                max_total_chars=max_total_chars,
            )
            logger.info(f"[BatchRunner] repo_aware mode initialized (max_files={self.retriever_max_files})")
        except Exception as e:
            logger.error(f"[BatchRunner] Failed to initialize repo_aware components: {e}. Falling back to issue_only.")
            self.mode = "issue_only"

    def _load_raw_lookup(self):
        """Tải dữ liệu raw để trích xuất base_code nếu dataset đã làm sạch không lưu trực tiếp code."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        raw_path = os.path.join(base_dir, "data", "raw", "all_crawled_raw.json")
        if os.path.exists(raw_path):
            try:
                with open(raw_path, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                    if isinstance(raw_list, list):
                        for r in raw_list:
                            rid = str(r.get("id", ""))
                            self.raw_lookup[rid] = r
                            norm_id = rid.replace("__", "_").replace("-", "_").lower()
                            self.raw_lookup[norm_id] = r
                logger.info(f"Loaded raw base_code lookup with {len(raw_list)} items for White-box analysis.")
            except Exception as e:
                logger.warning(f"Could not load raw base_code lookup from {raw_path}: {e}")

    def load_checkpoint(self) -> Dict[str, Any]:
        """Tải tiến độ đã xử lý từ trước."""
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded checkpoint with {len(data)} completed issues from {self.checkpoint_path}.")
                    return data
            except Exception as e:
                logger.warning(f"Failed to read checkpoint: {e}. Starting fresh.")
        return {}

    def save_checkpoint(self, checkpoint_data: Dict[str, Any]):
        """Lưu tiến độ hiện tại xuống ổ đĩa."""
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

    def process_issue(self, issue_record: Dict[str, Any], max_retries: int = 5) -> Dict[str, Any]:
        """Chạy analyzer cho một issue đơn lẻ với cơ chế retry và xử lý rate-limit thông minh."""
        issue_id = issue_record.get("id") or issue_record.get("issue_id") or "unknown_issue"
        record_to_use = dict(issue_record)

        if self.include_base_code:
            # 1. Thử lấy từ raw_lookup nếu có
            if not record_to_use.get("base_code") and not record_to_use.get("changes"):
                norm_id = str(issue_id).replace("__", "_").replace("-", "_").lower()
                if norm_id in self.raw_lookup:
                    raw_rec = self.raw_lookup[norm_id]
                    if raw_rec.get("changes"):
                        record_to_use["changes"] = raw_rec["changes"]
                    if raw_rec.get("base_code"):
                        record_to_use["base_code"] = raw_rec["base_code"]

            # 2. Nếu vẫn chưa có base_code, tự động gọi GitHub API (kèm cache) để tải
            if not record_to_use.get("base_code") and not record_to_use.get("changes"):
                try:
                    from analyzer.base_code_fetcher import GitHubBaseCodeFetcher
                    fetched_code = GitHubBaseCodeFetcher.fetch_base_code(record_to_use)
                    if fetched_code:
                        record_to_use["base_code"] = fetched_code
                except Exception as ex:
                    logger.warning(f"Could not fetch base_code from GitHub API for {issue_id}: {ex}")

        # -----------------------------------------------------------------------
        # repo_aware mode: Repository Context Retrieval (anti-leakage pipeline)
        # -----------------------------------------------------------------------
        retrieval_metadata: Dict[str, Any] = {
            "mode": self.mode,
            "repository_context_status": "skipped",
        }
        repo_context_text: Optional[str] = None

        if self.mode == "repo_aware" and self._retriever and self._context_builder:
            repo = (
                record_to_use.get("repo")
                or (record_to_use.get("repository") or {}).get("full_name", "")
            )
            base_commit = record_to_use.get("base_commit", "")
            issue_title = record_to_use.get("title", "")
            issue_body = record_to_use.get("body", "")

            if repo and base_commit:
                try:
                    # Bước 1: Lấy repository tree @ base_commit (KHÔNG dùng PR info)
                    from analyzer.repo_provider import get_repo_tree
                    logger.info(f"[repo_aware] Fetching tree for {repo}@{base_commit[:8]}...")
                    repo_tree = get_repo_tree(repo, base_commit)

                    if not repo_tree:
                        logger.warning(f"[repo_aware] Empty tree for {issue_id}. Falling back to issue_only.")
                        retrieval_metadata["repository_context_status"] = "fallback_issue_only"
                        retrieval_metadata["fallback_reason"] = "empty_tree"
                    else:
                        # Bước 2: LLM Context Retriever — chọn file dựa trên issue + tree
                        # KHÔNG truyền vào bất kỳ thông tin PR/solution nào
                        retrieval_result = self._retriever.retrieve(
                            repo=repo,
                            base_commit=base_commit,
                            issue_title=issue_title,
                            issue_body=issue_body,
                            repository_tree=repo_tree,
                            issue_id=issue_id,
                        )
                        retrieval_metadata["retriever_model"] = retrieval_result.get("retriever_model")
                        retrieval_metadata["retriever_prompt_version"] = retrieval_result.get("retriever_prompt_version")
                        retrieval_metadata["retrieval_status"] = retrieval_result.get("status")

                        if retrieval_result["status"] == "success":
                            selected = retrieval_result["selected_files"]
                            retrieval_metadata["retrieved_files"] = [
                                {"path": f["path"], "reason": f["reason"]}
                                for f in selected
                            ]

                            # Bước 3: Fetch nội dung file @ base_commit và build context
                            context_result = self._context_builder.build(
                                repo=repo,
                                base_commit=base_commit,
                                issue_title=issue_title,
                                issue_body=issue_body,
                                selected_files=selected,
                                repository_tree=repo_tree,
                            )
                            repo_context_text = context_result.get("context_text", "")

                            # Ghi start/end line vào retrieved_files metadata
                            for snippet in context_result.get("file_snippets", []):
                                for rf in retrieval_metadata.get("retrieved_files", []):
                                    if rf["path"] == snippet["path"]:
                                        rf["start_line"] = snippet["start_line"]
                                        rf["end_line"] = snippet["end_line"]

                            retrieval_metadata["repository_context_status"] = "success"
                            retrieval_metadata["files_included"] = context_result.get("files_included", 0)
                            retrieval_metadata["files_skipped"] = context_result.get("files_skipped", [])
                            retrieval_metadata["context_total_chars"] = context_result.get("total_chars", 0)
                            logger.info(
                                f"[repo_aware] Context built for {issue_id}: "
                                f"{context_result.get('files_included', 0)} files, "
                                f"{context_result.get('total_chars', 0)} chars"
                            )
                        else:
                            logger.warning(
                                f"[repo_aware] Retriever failed for {issue_id} "
                                f"(status={retrieval_result['status']}). Falling back to issue_only."
                            )
                            retrieval_metadata["repository_context_status"] = "fallback_issue_only"
                            retrieval_metadata["fallback_reason"] = retrieval_result.get("error")

                except Exception as e:
                    logger.error(f"[repo_aware] Retrieval error for {issue_id}: {e}. Falling back to issue_only.")
                    retrieval_metadata["repository_context_status"] = "fallback_issue_only"
                    retrieval_metadata["fallback_reason"] = str(e)
            else:
                logger.warning(f"[repo_aware] Missing repo/base_commit for {issue_id}. Falling back to issue_only.")
                retrieval_metadata["repository_context_status"] = "fallback_issue_only"
                retrieval_metadata["fallback_reason"] = "missing_repo_or_base_commit"

        # -----------------------------------------------------------------------
        # Build final prompt (issue_only hoặc repo_aware với repository context)
        # -----------------------------------------------------------------------
        sys_prompt, user_prompt = self.builder.build_prompts(
            record_to_use,
            include_base_code=self.include_base_code,
            repo_context_text=repo_context_text,
        )

        # Log chi tiết Input của issue
        if self.verbose:
            logger.info(
                f"\n{'='*35} [INPUT PROMPT: {issue_id}] {'='*35}\n"
                f"{user_prompt}\n"
                f"{'='*85}"
            )

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Issue {issue_id}: Sending request to LLM (Attempt {attempt}/{max_retries}, Temp: {self.temperature})...")
                llm_res = self.client.generate(sys_prompt, user_prompt, temperature=self.temperature)
                raw_text = llm_res.get("raw_text", "")

                # Log chi tiết Output thô của LLM
                if self.verbose:
                    logger.info(
                        f"\n{'-'*35} [OUTPUT LLM: {issue_id}] {'-'*35}\n"
                        f"{raw_text.strip()}\n"
                        f"{'-'*85}"
                    )

                parsed_json = OutputParser.parse_llm_json(raw_text)

                is_valid, errors = ProfileValidator.validate(parsed_json)
                if not is_valid:
                    raise ValueError(f"Profile validation failed: {'; '.join(errors)}")

                logger.info(f"Issue {issue_id}: Successfully generated profile (Latency: {llm_res.get('latency_ms', 0)}ms)")
                return {
                    "issue_id": issue_id,
                    "model": llm_res.get("model", "unknown"),
                    "prompt_version": self.prompt_version,
                    "profile": parsed_json,
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "tokens_prompt": llm_res.get("prompt_tokens", 0),
                        "tokens_completion": llm_res.get("completion_tokens", 0),
                        "latency_ms": llm_res.get("latency_ms", 0),
                        "temperature": self.temperature,
                        "input_prompt": user_prompt,
                        "raw_output": raw_text,
                        "status": "success",
                        "error_message": None,
                        "retrieval": retrieval_metadata,
                    }
                }


            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "resourceexhausted" in err_str.lower() or "quota" in err_str.lower()

                if is_rate_limit:
                    sleep_time = 32  # Google Gemini Free tier yêu cầu ~25-30s cooldown khi vượt 5 RPM
                    logger.warning(
                        f"[RATE LIMIT 429] Quota exceeded for issue {issue_id}. "
                        f"Free tier limit reached. Cooling down for {sleep_time}s before retry {attempt + 1}/{max_retries}..."
                    )
                else:
                    sleep_time = 2 ** attempt
                    logger.warning(f"Issue {issue_id} Attempt {attempt}/{max_retries} failed: {e}. Retrying in {sleep_time}s...")

                if attempt == max_retries:
                    logger.error(f"Issue {issue_id} failed permanently after {max_retries} attempts.")
                    return {
                        "issue_id": issue_id,
                        "model": "error",
                        "prompt_version": self.prompt_version,
                        "profile": None,
                        "metadata": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "temperature": self.temperature,
                            "input_prompt": user_prompt,
                            "status": "error",
                            "error_message": err_str,
                            "retrieval": retrieval_metadata,
                        }
                    }

                time.sleep(sleep_time)

    def run_batch(
        self,
        issues: List[Dict[str, Any]],
        limit: Optional[int] = None,
        delay_seconds: float = 12.0
    ) -> List[Dict[str, Any]]:
        """Chạy phân tích cho toàn bộ danh sách issues với cơ chế pacing tránh rate-limit."""
        checkpoint = self.load_checkpoint()
        results = list(checkpoint.values())
        processed_ids = set(checkpoint.keys())

        target_issues = issues[:limit] if limit else issues
        remaining_count = sum(1 for rec in target_issues if rec.get("id") not in processed_ids)
        logger.info(
            f"Starting batch analysis on {len(target_issues)} issues "
            f"(Prompt: {self.prompt_version}, Already completed: {len(processed_ids)}, Remaining: {remaining_count}, Delay: {delay_seconds}s)..."
        )

        for idx, rec in enumerate(target_issues, 1):
            rec_id = rec.get("id") or rec.get("issue_id")
            if rec_id in processed_ids:
                continue

            logger.info(f"[{idx}/{len(target_issues)}] Analyzing issue {rec_id}...")
            out = self.process_issue(rec)
            checkpoint[rec_id] = out
            results.append(out)

            # Lưu checkpoint ngay sau mỗi issue
            self.save_checkpoint(checkpoint)

            # Pacing delay giữa các issue để tuân thủ hạn mức Free Tier (5 requests/min)
            if delay_seconds > 0 and idx < len(target_issues):
                logger.info(f"Pacing: waiting {delay_seconds:.1f}s before next request (respecting API limits)...")
                time.sleep(delay_seconds)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        label_part = f"_{self.run_label}" if self.run_label else ""
        final_file = os.path.join(self.output_dir, f"analyzer_results_{self.prompt_version}{label_part}_{timestamp_str}.json")
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"Batch completed! Total results: {len(results)}. Saved to {final_file}")
        return results


def main():
    parser = argparse.ArgumentParser(description="Batch Runner for RAAC Requirement Analyzer")
    parser.add_argument("--input", default="data/cleaned/cleaned_benchmark.json", help="Cleaned dataset path")
    parser.add_argument("--provider", default=None, help="LLM provider: mock | openai | gemini | 9router | anthropic")
    parser.add_argument("--model", default=None, help="Tùy chọn ghi đè model ID (ví dụ: ag/gemini-3.8-flash, ag/claude-sonnet-4-6)")
    parser.add_argument("--version", default="v3", choices=["v1", "v2", "v3"], help="Prompt version: v1 | v2 | v3 (mặc định: v3)")
    parser.add_argument("--temperature", type=float, default=None, help="Tùy chọn ghi đè temperature (mặc định: 0.0 cho v3, 0.1 cho v1/v2)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of issues to process")
    parser.add_argument("--run-label", default=None, help="Nhãn đợt chạy (ví dụ: run1, run2) phục vụ đánh giá agreement")
    parser.add_argument("--checkpoint", default=None, help="Tùy chọn chỉ định đường dẫn file checkpoint")
    parser.add_argument("--clean-checkpoint", action="store_true", help="Xóa checkpoint cũ để chạy lại từ đầu")
    parser.add_argument("--include-base-code", action="store_true", default=False, help="Đính kèm base_code (mã nguồn trước khi sửa/merge) vào prompt phân tích")
    parser.add_argument("--quiet", action="store_true", help="Tắt hiển thị chi tiết input/output của từng issue lên console")
    parser.add_argument("--delay", type=float, default=None, help="Delay (giây) giữa các requests (mặc định: 13s cho Gemini Free, 1s cho 9router/OpenAI, 0s cho mock)")
    # repo_aware mode flags
    parser.add_argument(
        "--mode",
        default="issue_only",
        choices=["issue_only", "repo_aware"],
        help=(
            "Pipeline mode: "
            "'issue_only' (default) = original behavior, issue title+body only. "
            "'repo_aware' = fetch repo tree @ base_commit → LLM retriever → code context → analyzer. "
            "Anti-leakage guaranteed: no PR info used."
        )
    )
    parser.add_argument("--max-files", type=int, default=5, help="(repo_aware) Số file tối đa LLM retriever chọn (mặc định: 5)")
    parser.add_argument("--max-chars-per-file", type=int, default=12000, help="(repo_aware) Số ký tự tối đa mỗi file (mặc định: 12000)")
    parser.add_argument("--max-total-chars", type=int, default=40000, help="(repo_aware) Tổng số ký tự tối đa cho toàn bộ context (mặc định: 40000)")
    args = parser.parse_args()

    # Xác định file checkpoint
    label_suffix = f"_{args.run_label}" if args.run_label else ""
    mode_suffix = f"_{args.mode}" if args.mode != "issue_only" else ""
    checkpoint_file = args.checkpoint or f"data/analyzer_outputs/checkpoint_{args.version}{label_suffix}{mode_suffix}.json"

    if args.clean_checkpoint and os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
        logger.info(f"Cleared existing checkpoint: {checkpoint_file}")

    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}. Run crawl_dataset.py and clean_dataset.py first!")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Hỗ trợ cả định dạng phẳng (list) và định dạng gom nhóm theo repo (dict với key "repos")
    if isinstance(data, dict) and "repos" in data:
        issues = []
        for r in data["repos"]:
            repo_name = r.get("repo", "")
            repo_url = r.get("repo_url", "")
            for iss in r.get("issues", []):
                iss_copy = dict(iss)
                iss_copy["repo"] = repo_name
                iss_copy["repository"] = {"full_name": repo_name, "url": repo_url}
                issues.append(iss_copy)
    elif isinstance(data, list):
        issues = data
    else:
        logger.error(f"Unrecognized dataset format in {args.input}")
        return

    # Tự động điều chỉnh delay mặc định theo từng provider
    active_provider = (args.provider or os.getenv("LLM_PROVIDER", "mock")).lower()
    if args.delay is not None:
        delay = args.delay
    elif active_provider == "mock":
        delay = 0.0
    elif active_provider in ("gemini", "google"):
        delay = 13.0
    else:
        delay = 1.0

    llm_client = get_llm_client(args.provider)
    if args.model and hasattr(llm_client, "model"):
        llm_client.model = args.model
        logger.info(f"Using model override: {llm_client.model}")

    runner = BatchRunner(
        llm_client=llm_client,
        prompt_version=args.version,
        checkpoint_path=checkpoint_file,
        temperature=args.temperature,
        run_label=args.run_label,
        include_base_code=args.include_base_code,
        verbose=not args.quiet,
        mode=args.mode,
        retriever_max_files=args.max_files,
        context_max_chars_per_file=args.max_chars_per_file,
        context_max_total_chars=args.max_total_chars,
    )
    runner.run_batch(issues, limit=args.limit, delay_seconds=delay)


if __name__ == "__main__":
    main()
