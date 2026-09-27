"""Apply filter_rules.md to raw batch 1, retaining an auditable decision log."""
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from scripts.file_parser import FileParser
from scripts.group_dataset_by_repo import group_by_repo

ROOT = Path(__file__).resolve().parents[1]
# Batch-specific review of issue text, PR description and available patches.
REJECT_REVIEW = {
    "psf_requests_1659": "Release version/build metadata only; no implementation of the requested certificate automation.",
    "scikit-learn_scikit-learn_13499": "Documentation and grammatical correction inside a module docstring only.",
    "scikit-learn_scikit-learn_29587": "Only clarifies multithreading in docstrings; no runtime change.",
    "pallets_flask_1809": "API documentation and cosmetic formatting only.",
    "pallets_flask_1151": "Context documentation, docstrings and error-message wording only.",
}
REPRESENTATIVES = {
    ("pallets/flask", 3923): "pallets_flask_593",
    ("encode/django-rest-framework", 4192): "encode_django-rest-framework_2848",
}
SHORT_REVIEW = {
    "psf_requests_2025": "Short but explicit JSON upload feature request with requests.post(json=...) example."
}


def source_file(file):
    """Do not confuse executable bundled docs UI with repository documentation."""
    name = file["filename"].lower()
    if name.startswith(("doc/", "docs/", "examples/")) or file.get("is_test"):
        return False
    return name.endswith(tuple(FileParser.SOURCE_EXTENSIONS) + (".pyx", ".pxd", ".pyx.tp", ".pxd.tp")) or (
        "/templates/" in name and name.endswith(".html")
    )


def substantive(file):
    patch = file.get("patch_snippet") or ""
    if not source_file(file) or not patch or file.get("is_comment_only"):
        return False
    if FileParser.is_comment_or_doc_patch(patch):
        return False
    added, removed = [], []
    for line in patch.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            (added if line[0] == "+" else removed).append(re.sub(r"\s+", "", line[1:]))
    return "".join(added) != "".join(removed)


def evaluate(record):
    issue, pr = record["issue"], record["linked_pr"]
    if not pr.get("merged") or pr.get("base_branch") not in {"main", "master"}:
        return "no_merged_main_pr", "Requires merged PR targeting main/master."
    labels = {str(x.get("name", "") if isinstance(x, dict) else x).lower() for x in issue["labels"]}
    if labels & {"invalid", "wontfix", "duplicate"}:
        return "excluded_label", "Issue has an exclusion label."
    if record["id"] in REJECT_REVIEW:
        return "non_substantive_review", REJECT_REVIEW[record["id"]]
    words = len(((issue.get("title") or "") + " " + (issue.get("body") or "")).split())
    if words < 20 and record["id"] not in SHORT_REVIEW:
        return "insufficient_context", "Under 20 words without a reviewed completeness exception."
    files = record["changes"]["files"]
    code = [f for f in files if substantive(f)]
    if not code:
        return "no_substantive_source", "No substantive executable-source change in available patches."
    if record["changes"]["additions"] + record["changes"]["deletions"] < 3:
        return "under_3_lines", "Total PR additions plus deletions below 3."
    if pr.get("is_bot"):
        return "bot_requires_review", "Bot-authored PR requires review for a substantive breaking-change exception."
    representative = REPRESENTATIVES.get((record["repository"]["full_name"], pr["pr_number"]))
    if representative and representative != record["id"]:
        return "shared_pr", f"Retained {representative}, whose requirement directly matches the PR implementation."
    return "accepted", SHORT_REVIEW.get(record["id"], "Merged main/master PR, sufficient requirement context and substantive code changes.")


def main():
    source = ROOT / "data/raw/all_crawled_raw_1.json"
    output = ROOT / "data/cleaned/cleaned_benchmark.json"
    report_path = output.with_name("cleaned_benchmark_filter_report.json")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    rows = json.loads(source.read_text(encoding="utf-8"))
    evidence = json.loads((ROOT / "data/raw/resolved_candidates_1.json").read_text(encoding="utf-8"))
    evidence = {r["id"]: r for r in evidence}
    kept, decisions, seen = [], [], set()
    for row in rows:
        candidate = evidence[row["id"]]
        closer = candidate["provenance"]["closing_event"]["closer"]
        assert closer["merged"] and closer["number"] == row["linked_pr"]["pr_number"]
        assert closer["repository"]["nameWithOwner"] == row["repository"]["full_name"]
        assert candidate["issue"]["title"] == row["issue"]["title"]
        category, reason = evaluate(row)
        if row["id"] in seen:
            category, reason = "duplicate_id", "Duplicate issue ID."
        seen.add(row["id"])
        if category == "accepted":
            kept.append(row)
        decisions.append({"id": row["id"], "decision": category, "reason": reason})
    grouped = group_by_repo(kept, dataset_version="v1-filtered-raw-1", include_details=False)
    by_url = {r["linked_pr"]["pr_url"]: r for r in kept}
    for repo in grouped["repos"]:
        for issue in repo["issues"]:
            files = by_url[issue["url"]]["changes"]["files"]
            issue["has_test"] = any(f["is_test"] for f in files)
            issue["test_files"] = [f["filename"] for f in files if f["is_test"]]
            issue["source_files"] = [f["filename"] for f in files if source_file(f)]
            issue["doc_files"] = [f["filename"] for f in files if f["is_doc"] and not source_file(f)]
    report = {
        "input": str(source), "input_sha256": source_hash,
        "rules": str(ROOT / "docs/filter_rules.md"),
        "total_raw": len(rows), "kept": len(kept), "rejected": len(rows) - len(kept),
        "counts": dict(Counter(d["decision"] for d in decisions)),
        "repositories": {r["repo"]: len(r["issues"]) for r in grouped["repos"]},
        "limitations": ["Offline review of saved metadata and patch snippets, not full diffs or live external-link checks.",
                        "Three-line minimum applies to total PR additions plus deletions; substantive source change is required separately.",
                        "No filtering by RAAC score or test presence; Cython and runtime templates count as executable source."],
        "decisions": decisions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    for path, data in [(output, grouped), (report_path, report)]:
        if path.exists():
            backup = path.with_name(path.stem + datetime.now().strftime("_backup_%Y%m%d_%H%M%S_%f") + ".json")
            backup.write_bytes(path.read_bytes())
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8")) == data
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    assert len(by_url) == len(kept), "Duplicate PR in cleaned data"
    assert grouped["total_issues"] == len(kept)
    print(json.dumps({k: v for k, v in report.items() if k != "decisions"}, indent=2))


if __name__ == "__main__":
    main()