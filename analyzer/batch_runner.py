"""
Module: batch_runner.py
Điều phối chạy batch Requirement Analyzer cho toàn bộ benchmark dataset:
- Quản lý checkpoint (lưu tiến độ từng issue, tự động resume khi chạy lại).
- Tự động retry khi gặp lỗi mạng/rate-limit.
- Kiểm tra tính hợp lệ qua ProfileValidator.
- Xuất kết quả chuẩn hóa vào data/analyzer_outputs/.
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
        prompt_version: str = "v2",
        output_dir: str = "data/analyzer_outputs",
        checkpoint_path: str = "data/analyzer_outputs/checkpoint.json"
    ):
        self.client = llm_client
        self.prompt_version = prompt_version
        self.output_dir = output_dir
        self.checkpoint_path = checkpoint_path
        self.builder = PromptBuilder(prompt_version=prompt_version)
        os.makedirs(self.output_dir, exist_ok=True)

    def load_checkpoint(self) -> Dict[str, Any]:
        """Tải tiến độ đã xử lý từ trước."""
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded checkpoint with {len(data)} completed issues.")
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
        issue_id = issue_record.get("id")
        sys_prompt, user_prompt = self.builder.build_prompts(issue_record)

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Issue {issue_id}: Sending request to LLM (Attempt {attempt}/{max_retries})...")
                llm_res = self.client.generate(sys_prompt, user_prompt)
                raw_text = llm_res.get("raw_text", "")
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
                        "status": "success",
                        "error_message": None
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
                            "status": "error",
                            "error_message": err_str
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
            f"(Already completed: {len(processed_ids)}, Remaining: {remaining_count}, Delay between requests: {delay_seconds}s)..."
        )

        for idx, rec in enumerate(target_issues, 1):
            rec_id = rec.get("id")
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
        final_file = os.path.join(self.output_dir, f"analyzer_results_{self.prompt_version}_{timestamp_str}.json")
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"Batch completed! Total results: {len(results)}. Saved to {final_file}")
        return results


def main():
    parser = argparse.ArgumentParser(description="Batch Runner for RAAC Requirement Analyzer")
    parser.add_argument("--input", default="data/cleaned/cleaned_benchmark.json", help="Cleaned dataset path")
    parser.add_argument("--provider", default=None, help="LLM provider: mock | openai | gemini")
    parser.add_argument("--version", default="v2", help="Prompt version: v1 | v2")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of issues to process")
    parser.add_argument("--clean-checkpoint", action="store_true", help="Xóa checkpoint cũ để chạy lại từ đầu")
    parser.add_argument("--delay", type=float, default=13.0, help="Delay (giây) giữa các requests để tránh rate limit (mặc định: 13s cho Gemini Free Tier 5 RPM)")
    args = parser.parse_args()

    checkpoint_file = "data/analyzer_outputs/checkpoint.json"
    if args.clean_checkpoint and os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
        logger.info("Cleared existing checkpoint.")

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

    # Nếu dùng mock thì không cần delay
    delay = 0.0 if args.provider == "mock" else args.delay

    llm_client = get_llm_client(args.provider)
    runner = BatchRunner(llm_client=llm_client, prompt_version=args.version)
    runner.run_batch(issues, limit=args.limit, delay_seconds=delay)


if __name__ == "__main__":
    main()
