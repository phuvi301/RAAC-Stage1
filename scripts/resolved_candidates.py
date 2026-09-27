"""Verify resolution using GitHub ClosedEvent.closer, not mere PR mentions."""
import copy
import time
from datetime import datetime, timezone

from scripts.github_api import GitHubAPIClient
from scripts.pr_parser import PRParser
from scripts.file_parser import FileParser

FIELDS = """number title body state stateReason createdAt closedAt url
 labels(first:100){nodes{name}}
 repository{nameWithOwner url}
 timelineItems(last:1,itemTypes:[CLOSED_EVENT]){nodes{
 ... on ClosedEvent{createdAt closer{__typename ... on PullRequest{number url merged mergedAt repository{nameWithOwner}}}}
 }}"""


def graphql(client, query, variables):
    response = client.session.post("https://api.github.com/graphql",
                                   json={"query": query, "variables": variables}, timeout=60)
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"]))
    return data["data"]


def closing_pr(issue):
    if issue.get("state") != "CLOSED" or issue.get("stateReason") != "COMPLETED":
        return None
    events = issue["timelineItems"]["nodes"]
    closer = events[-1].get("closer") if events else None
    if not closer or closer.get("__typename") != "PullRequest" or not closer.get("merged"):
        return None
    if closer["repository"]["nameWithOwner"] != issue["repository"]["nameWithOwner"]:
        return None
    return closer


def collect(raw, repos, load, save):
    client = GitHubAPIClient()
    original = {r["id"]: r for r in load(raw / "balanced_candidates_1.json", [])}
    excluded = {r["id"] for r in load(raw / "all_crawled_raw.json", [])}
    path = raw / "resolved_candidates_1.json"
    records = load(path, [])
    seen = {r["id"] for r in records} | excluded
    progress_path = raw / "resolved_progress_1.json"
    done = load(progress_path, [])

    def accept(issue):
        repo = issue["repository"]["nameWithOwner"]
        rid = repo.replace("/", "_") + "_" + str(issue["number"])
        pr = closing_pr(issue)
        if rid in seen or not pr or not issue.get("body"):
            return
        owner, name = repo.split("/")
        detail = client.get_pull_request(owner, name, pr["number"])
        if not detail or not detail.get("merged") or not detail.get("merged_at"):
            raise RuntimeError(f"PR detail verification failed: {rid}")
        files = []
        for page in range(1, 31):
            batch = client.get(f"/repos/{repo}/pulls/{pr['number']}/files", {"per_page": 100, "page": page})
            if not isinstance(batch, list):
                raise RuntimeError(f"Files fetch failed: {rid}")
            files.extend(batch)
            if len(batch) < 100:
                break
        if len(files) != detail["changed_files"]:
            raise RuntimeError(f"Incomplete PR files: {rid}")
        meta = PRParser.parse_pr_metadata(detail)
        summary = FileParser.parse_changed_files(files, meta["base_commit"], repo)
        record = {"id": rid, "base_commit": meta["base_commit"],
            "issue": {"number": issue["number"], "title": issue["title"], "body": issue["body"],
                "labels": [l["name"] for l in issue["labels"]["nodes"]], "state": "closed",
                "state_reason": "completed", "created_at": issue["createdAt"],
                "closed_at": issue["closedAt"], "url": issue["url"]},
            "repository": {"owner": owner, "name": name, "full_name": repo, "url": issue["repository"]["url"]},
            "linked_pr": meta,
            "changes": {"files_changed_count": summary["total_files"], "additions": summary["total_additions"],
                        "deletions": summary["total_deletions"], "files": summary["files"]},
            "tests": {"test_files_changed": summary["test_files_changed"],
                      "test_files_count": summary["test_files_count"], "test_files": summary["test_file_list"]},
            "provenance": {"fetched_at": datetime.now(timezone.utc).isoformat(),
                "resolution_evidence": "GitHub GraphQL latest ClosedEvent.closer is this merged PR",
                "closing_event": issue["timelineItems"]["nodes"][-1],
                "base_code_note": "Patch-derived excerpts, not complete source files"}}
        previous = original.get(rid, {})
        if previous.get("issue", {}).get("body") == issue["body"] and previous.get("issue", {}).get("title") == issue["title"]:
            for key in ("screening", "screening_metadata"):
                if key in previous:
                    record[key] = copy.deepcopy(previous[key])
        records.append(record)
        seen.add(rid)
        save(path, records)
        print(f"Verified {len(records)}: {rid} <- merged PR #{pr['number']}", flush=True)

    # Revalidate old candidates first so reusable annotations are retained.
    for repo in repos:
        key = repo + ":original"
        if key not in done:
            numbers = [r["issue"]["number"] for r in original.values() if r["repository"]["full_name"] == repo]
            owner, name = repo.split("/")
            for start in range(0, len(numbers), 20):
                fields = " ".join(f"i{n}:issue(number:{n}){{{FIELDS}}}" for n in numbers[start:start + 20])
                query = 'query($owner:String!,$name:String!){repository(owner:$owner,name:$name){' + fields + '}}'
                data = graphql(client, query, {"owner": owner, "name": name})
                for issue in data["repository"].values():
                    if issue:
                        accept(issue)
            done.append(key)
            save(progress_path, done)
    # Expand across topics; only verified closures enter the scoring pool.
    for repo in repos:
        for keyword in ("", "security", "authentication", "architecture", "performance", "concurrency"):
            key = repo + ":search:" + keyword
            if key in done:
                continue
            query = 'query($q:String!){search(query:$q,type:ISSUE,first:60){nodes{... on Issue{' + FIELDS + '}}}}'
            data = graphql(client, query, {"q": f"repo:{repo} is:issue is:closed linked:pr {keyword} sort:comments-desc"})
            for issue in data["search"]["nodes"]:
                if issue:
                    accept(issue)
            done.append(key)
            save(progress_path, done)
            time.sleep(2)
    return path, records


if __name__ == "__main__":
    from scripts.crawl_balanced_dataset import RAW, REPOS, load, save
    collect(RAW, REPOS, load, save)