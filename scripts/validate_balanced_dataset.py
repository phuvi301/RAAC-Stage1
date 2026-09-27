"""Validate saved raw dataset and recompute its reported distributions."""
import json
from collections import Counter
from pathlib import Path


def main():
    raw = Path(__file__).resolve().parents[1] / "data" / "raw"
    read = lambda name: json.loads((raw / name).read_text(encoding="utf-8"))
    rows = read("all_crawled_raw_1.json")
    report = read("all_crawled_raw_1_report.json")
    previous = read("all_crawled_raw.json")
    candidates = {r["id"]: r for r in read(report.get("candidate_file", "balanced_candidates_1.json"))}
    assert len(rows) == len({r["id"] for r in rows}) == 120
    assert not {r["id"] for r in previous} & {r["id"] for r in rows}
    assert dict(Counter(r["repository"]["full_name"] for r in rows)) == report["repositories"]
    assert len(report["repositories"]) == 5
    for r in rows:
        assert r == candidates[r["id"]]
        if report.get("eligibility"):
            assert r["issue"]["state"] == "closed" and r["issue"]["state_reason"] == "completed"
            assert r["linked_pr"]["merged"] is True and r["linked_pr"]["merged_at"]
            closer = r["provenance"]["closing_event"]["closer"]
            assert closer["merged"] is True and closer["url"] == r["linked_pr"]["pr_url"]
            assert r["base_commit"] == r["linked_pr"]["base_commit"] and len(r["base_commit"]) == 40
            assert r["changes"]["files_changed_count"] == len(r["changes"]["files"])
        assert r["issue"]["body"] and r["issue"]["title"]
        assert r["issue"]["url"] == f"https://github.com/{r['repository']['full_name']}/issues/{r['issue']['number']}"
        if "screening" not in r:
            assert report.get("status") == "INCOMPLETE_SCORING_NOT_AXIS_BALANCED"
            continue
        assert r["screening_metadata"]["status"] == "provisional_llm_not_ground_truth"
        for a in "CTSA":
            assert type(r["screening"][a]["score"]) is int
            assert 1 <= r["screening"][a]["score"] <= 5
            assert r["screening"][a]["evidence"].strip()
    for a in "CTSA":
        histogram = {str(s): sum(r["screening"][a]["score"] == s for r in rows if "screening" in r) for s in range(1, 6)}
        assert histogram == report.get("axes", report.get("axes_scored_subset_only"))[a]
    print("PASS: 120 unique new issues, five repos, saved candidates and reported distributions match")
    print("Scoring status:", report.get("status", "All issues provisionally scored"))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()