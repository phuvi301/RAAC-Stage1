"""
Script: scripts/run_analyzer_v3.py
Chuyên dụng để thực thi Requirement Analyzer với Prompt v3.0 (theo đặc tả prompts/requirement_analyzer_v3.md):
- Chuẩn hóa đầu vào JSON (không cắt ngắn body, task/repo/id/title/body chuẩn).
- Cố định temperature=0.0 theo khuyến nghị tái lập độ ổn định (Section 5).
- Tách biệt checkpoint riêng cho v3, hỗ trợ --run-label (run1, run2...) phục vụ so sánh độ nhất quán (inter-run agreement).
- Tích hợp công cụ so sánh đối chuẩn tự động (--compare) để tính Exact Agreement, MAE từng trục giữa các lần chạy.
- Thống kê phân bố điểm số 4 trục (C, T, S, A) ngay sau khi chạy xong.
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# Đảm bảo import được module từ thư mục gốc dự án
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from analyzer.llm_client import get_llm_client, BaseLLMClient
from analyzer.batch_runner import BatchRunner
from analyzer.validator import ProfileValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AnalyzerV3")


def load_dataset(file_path: str, repo_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Tải và trích xuất danh sách issue từ dataset benchmark."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file dataset: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    issues: List[Dict[str, Any]] = []
    if isinstance(data, dict) and "repos" in data:
        for r in data["repos"]:
            repo_name = r.get("repo", "")
            repo_url = r.get("repo_url", "")
            if repo_filter and repo_filter.lower() not in repo_name.lower():
                continue
            for iss in r.get("issues", []):
                iss_copy = dict(iss)
                iss_copy["repo"] = repo_name
                iss_copy["repository"] = {"full_name": repo_name, "url": repo_url}
                issues.append(iss_copy)
    elif isinstance(data, list):
        for item in data:
            repo_name = item.get("repo") or item.get("repository", {}).get("full_name", "")
            if repo_filter and repo_filter.lower() not in repo_name.lower():
                continue
            issues.append(item)
    else:
        raise ValueError(f"Định dạng dataset không hợp lệ trong {file_path}")

    return issues


def print_run_summary(results: List[Dict[str, Any]], elapsed_time: float):
    """In bảng tổng kết kết quả phân tích sau khi chạy xong."""
    total = len(results)
    successes = [r for r in results if r.get("profile") is not None]
    errors = total - len(successes)

    print("\n" + "=" * 65)
    print("           TỔNG KẾT KẾT QUẢ REQUIREMENT ANALYZER V3")
    print("=" * 65)
    print(f"Tổng số issue xử lý:     {total}")
    print(f"Thành công:              {len(successes)} ({len(successes)/total*100:.1f}%)" if total else "0")
    print(f"Lỗi:                     {errors}")
    print(f"Thời gian thực thi:      {elapsed_time:.1f}s")

    if not successes:
        print("=" * 65)
        return

    axes = ["complexity", "testability", "security_sensitivity", "architecture_impact"]
    axis_labels = {
        "complexity": "C (Complexity)",
        "testability": "T (Testability)",
        "security_sensitivity": "S (Security)",
        "architecture_impact": "A (Architecture)"
    }

    print("\n--- PHÂN BỐ ĐIỂM SỐ 4 TRỤC (THANG 1 - 5) ---")
    print(f"{'Trục':<20} | {'1':<4} {'2':<4} {'3':<4} {'4':<4} {'5':<4} | {'Mean':<5}")
    print("-" * 55)

    for axis in axes:
        scores = []
        for r in successes:
            p = r.get("profile", {})
            ax_data = p.get(axis, {})
            score = ax_data.get("score")
            if isinstance(score, int) and 1 <= score <= 5:
                scores.append(score)

        if scores:
            dist = {i: scores.count(i) for i in range(1, 6)}
            mean_val = sum(scores) / len(scores)
            print(f"{axis_labels[axis]:<20} | {dist[1]:<4} {dist[2]:<4} {dist[3]:<4} {dist[4]:<4} {dist[5]:<4} | {mean_val:.2f}")
        else:
            print(f"{axis_labels[axis]:<20} | Không có dữ liệu hợp lệ")

    # Thống kê token và độ trễ
    latencies = [r.get("metadata", {}).get("latency_ms", 0) for r in successes if r.get("metadata")]
    p_tokens = [r.get("metadata", {}).get("tokens_prompt", 0) for r in successes if r.get("metadata")]
    c_tokens = [r.get("metadata", {}).get("tokens_completion", 0) for r in successes if r.get("metadata")]

    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        print(f"\nĐộ trễ trung bình mỗi issue:  {avg_lat:.0f} ms")
    if sum(p_tokens) > 0 or sum(c_tokens) > 0:
        print(f"Tổng tokens tiêu thụ:         Prompt: {sum(p_tokens):,} | Output: {sum(c_tokens):,}")

    print("=" * 65 + "\n")


def compare_runs(current_results: List[Dict[str, Any]], compare_file_path: str):
    """
    So sánh độ nhất quán (Inter-run Agreement / Stability) giữa hai lần chạy:
    Tính toán Exact Agreement từng trục, Exact Profile Agreement, và MAE theo chuẩn Section 5.
    """
    if not os.path.exists(compare_file_path):
        logger.error(f"Không tìm thấy file so sánh: {compare_file_path}")
        return

    try:
        with open(compare_file_path, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
    except Exception as e:
        logger.error(f"Không thể đọc file so sánh: {e}")
        return

    baseline_map = {r.get("issue_id"): r.get("profile") for r in baseline_data if r.get("profile")}
    current_map = {r.get("issue_id"): r.get("profile") for r in current_results if r.get("profile")}

    common_ids = sorted(list(set(baseline_map.keys()) & set(current_map.keys())))
    if not common_ids:
        print(f"[COMPARE] Không tìm thấy issue chung giữa 2 lần chạy để so sánh.")
        return

    print("\n" + "=" * 70)
    print(f"       SO SÁNH ĐỘ ĐỒNG THUẬN (INTER-RUN AGREEMENT / STABILITY)")
    print(f"       Giao nhau: {len(common_ids)} issues")
    print(f"       Baseline: {os.path.basename(compare_file_path)}")
    print("=" * 70)

    axes = ["complexity", "testability", "security_sensitivity", "architecture_impact"]
    axis_labels = {
        "complexity": "C (Complexity)",
        "testability": "T (Testability)",
        "security_sensitivity": "S (Security)",
        "architecture_impact": "A (Architecture)"
    }

    exact_matches = {ax: 0 for ax in axes}
    mae_diffs = {ax: 0.0 for ax in axes}
    exact_profiles_count = 0

    for iid in common_ids:
        p1 = baseline_map[iid]
        p2 = current_map[iid]

        all_axes_match = True
        for ax in axes:
            s1 = p1.get(ax, {}).get("score", 0)
            s2 = p2.get(ax, {}).get("score", 0)
            diff = abs(s1 - s2)
            mae_diffs[ax] += diff
            if diff == 0:
                exact_matches[ax] += 1
            else:
                all_axes_match = False

        if all_axes_match:
            exact_profiles_count += 1

    n = len(common_ids)
    print(f"\n{'Trục':<20} | {'Exact Match':<16} | {'Tỷ lệ Khớp (%)':<16} | {'MAE':<8}")
    print("-" * 70)
    for ax in axes:
        pct = (exact_matches[ax] / n) * 100
        mae = mae_diffs[ax] / n
        print(f"{axis_labels[ax]:<20} | {exact_matches[ax]}/{n:<14} | {pct:>6.2f}%          | {mae:.3f}")

    total_scores = n * 4
    total_exact_scores = sum(exact_matches.values())
    total_pct = (total_exact_scores / total_scores) * 100
    exact_profile_pct = (exact_profiles_count / n) * 100

    print("-" * 70)
    print(f"Tổng hợp toàn bộ 4 trục: {total_exact_scores}/{total_scores} scores giống nhau ({total_pct:.2f}%)")
    print(f"Tỷ lệ khớp toàn bộ profile (cả 4 trục cùng khớp): {exact_profiles_count}/{n} ({exact_profile_pct:.2f}%)")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="RAAC Requirement Analyzer v3 Runner — Chạy phân tích ổn định 4 trục theo đặc tả v3.0"
    )
    parser.add_argument(
        "--provider",
        default="9router",
        choices=["9router", "openai", "gemini", "anthropic", "mock"],
        help="LLM Provider kết nối (mặc định: 9router)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Tùy chọn ghi đè model (ví dụ: ag/gemini-3.8-flash, ag/claude-sonnet-4-6, gpt-4o-mini)"
    )
    parser.add_argument(
        "--input",
        default=os.path.join(BASE_DIR, "data", "cleaned", "cleaned_benchmark.json"),
        help="Đường dẫn file dataset benchmark đã làm sạch"
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(BASE_DIR, "data", "analyzer_outputs"),
        help="Thư mục lưu kết quả phân tích"
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Lọc chỉ chạy cho 1 repository cụ thể (ví dụ: requests, flask, django-rest-framework)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Giới hạn số lượng issue cần phân tích (thử nghiệm nhanh)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Nhiệt độ sinh LLM (mặc định: 0.0 theo chuẩn Section 5 để tối ưu tính tất định)"
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Nhãn đợt chạy (ví dụ: run1, run2) để lưu checkpoint và file kết quả độc lập"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Độ trễ (giây) giữa các requests (mặc định: 1s cho 9router/OpenAI, 13s cho Gemini Free, 0s cho mock)"
    )
    parser.add_argument(
        "--clean-checkpoint",
        action="store_true",
        help="Xóa checkpoint của đợt chạy này để bắt đầu lại từ đầu"
    )
    parser.add_argument(
        "--compare",
        default=None,
        help="Đường dẫn tới file kết quả của run trước để đo đạc độ ổn định/đồng thuận (Agreement Analysis)"
    )
    args = parser.parse_args()

    # 1. Tải danh sách issues
    logger.info(f"Đang tải dataset từ: {args.input}")
    issues = load_dataset(args.input, repo_filter=args.repo)
    if not issues:
        logger.error("Không tìm thấy issue nào phù hợp với điều kiện lọc!")
        return

    logger.info(f"Đã tải {len(issues)} issues sẵn sàng phân tích.")

    # 2. Xác định file checkpoint
    label_suffix = f"_{args.run_label}" if args.run_label else ""
    checkpoint_file = os.path.join(args.output_dir, f"checkpoint_v3{label_suffix}.json")

    if args.clean_checkpoint and os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
        logger.info(f"Đã xóa checkpoint: {checkpoint_file}")

    # 3. Tự động điều chỉnh delay
    active_provider = args.provider.lower()
    if args.delay is not None:
        delay = args.delay
    elif active_provider == "mock":
        delay = 0.0
    elif active_provider in ("gemini", "google"):
        delay = 13.0
    else:
        delay = 1.0

    # 4. Khởi tạo LLM Client
    llm_client = get_llm_client(args.provider)
    if args.model and hasattr(llm_client, "model"):
        llm_client.model = args.model
        logger.info(f"Đã áp dụng model override: {llm_client.model}")

    # 5. Chạy BatchRunner với prompt_version = "v3"
    runner = BatchRunner(
        llm_client=llm_client,
        prompt_version="v3",
        output_dir=args.output_dir,
        checkpoint_path=checkpoint_file,
        temperature=args.temperature,
        run_label=args.run_label
    )

    start_time = time.time()
    results = runner.run_batch(issues, limit=args.limit, delay_seconds=delay)
    elapsed = time.time() - start_time

    # 6. In tóm tắt kết quả
    print_run_summary(results, elapsed)

    # 7. So sánh nếu có yêu cầu --compare
    if args.compare:
        compare_runs(results, args.compare)


if __name__ == "__main__":
    main()
