#!/usr/bin/env python3
"""Check an explainer's code anchors against the repo they cite, and stamp the result.

An explainer's `orient-evidence` block lists code anchors as `path@sha[:L10-30]`. This asks git
whether each cited path has changed on the default branch since its sha, and whether the doc's
`verified_paths` have moved since `verified_sha`. With --write it stamps three frontmatter keys by
raw line edit (the vault is authoritative: never re-serialise YAML, so unknown keys survive):

    commits_behind:   commits on verified_paths since verified_sha
    drifted_evidence: [ids of code anchors whose path changed, vanished or whose sha is unknown]
    drift_checked:    today

orient reads those keys; it never runs git itself.

Usage:
    explain-drift.py <explainer.md>... [--write] [--json] [--no-fetch]
    explain-drift.py --all [--write] [--json] [--no-fetch]     every Engineering/*/explainers/*.md
Exit: 0 checked (drift is information, not failure) · 2 could not check something
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys

VAULT = pathlib.Path.home() / "Documents" / "obsidian"
WP = pathlib.Path.home() / ".claude" / "waypoint" / "wp.py"
CODE_REF = re.compile(r"^(.+?)@([0-9a-fA-F]{7,40})(?::(L\d+(?:-L?\d+)?))?$")
EVIDENCE = re.compile(r"```orient-evidence\n(.*?)```", re.S)


def sh(args, cwd=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def split_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return (m.group(1), m.end()) if m else (None, 0)


def fm_scalar(fm, key):
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", fm, re.M)
    return m.group(1).strip("'\"") if m else None


def fm_list(fm, key):
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm, re.M)
    if not m:
        return None
    inline = m.group(1).strip()
    if inline.startswith("["):
        body = inline.strip("[]").strip()
        return [x.strip().strip("'\"") for x in body.split(",") if x.strip()]
    items = []
    for line in fm[m.end():].split("\n")[1:]:
        item = re.match(r"^\s+-\s+(.+?)\s*$", line)
        if not item:
            break
        items.append(item.group(1).strip("'\""))
    return items


def service_of(path, fm):
    parts = path.resolve().parts
    if "Engineering" in parts:
        i = parts.index("Engineering")
        if len(parts) > i + 2 and parts[i + 2] == "explainers":
            return parts[i + 1]
    return fm_scalar(fm, "service") or fm_scalar(fm, "repo")


def repo_of(service):
    rc, out, err = sh(["python3", str(WP), "locate", service])
    if rc != 0:
        return None
    try:
        return pathlib.Path(json.loads(out)["repo"])
    except (ValueError, KeyError, TypeError):
        return None


def default_ref(repo):
    rc, out, _ = sh(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repo)
    if rc == 0 and out.strip():
        return out.strip()
    for ref in ("origin/main", "origin/master"):
        if sh(["git", "rev-parse", "--verify", "-q", ref], cwd=repo)[0] == 0:
            return ref
    return None


def commits_since(repo, sha, ref, path=None):
    args = ["git", "log", "--oneline", f"{sha}..{ref}"]
    if path:
        args += ["--", path]
    rc, out, _ = sh(args, cwd=repo)
    return None if rc != 0 else len([line for line in out.splitlines() if line.strip()])


def exists_at(repo, ref, path):
    return sh(["git", "cat-file", "-e", f"{ref}:{path}"], cwd=repo)[0] == 0


def check_anchor(repo, ref, item):
    m = CODE_REF.match(item["ref"].strip())
    if not m:
        return "unparseable", None
    path, sha = m.group(1), m.group(2)
    if not exists_at(repo, ref, path):
        return "gone", None
    n = commits_since(repo, sha, ref, path)
    if n is None:
        return "unknown", None
    return ("moved" if n > 0 else "ok"), n


def check(path, fetch):
    text = path.read_text()
    fm, body_at = split_frontmatter(text)
    if fm is None:
        return {"file": str(path), "error": "no frontmatter"}
    service = service_of(path, fm)
    if not service:
        return {"file": str(path), "error": "no service (path is not Engineering/<svc>/explainers, and no service: key)"}
    repo = repo_of(service)
    if not repo or not repo.is_dir():
        return {"file": str(path), "error": f"cannot locate repo for {service}"}
    if fetch:
        sh(["git", "fetch", "-q", "origin"], cwd=repo)
    ref = default_ref(repo)
    if not ref:
        return {"file": str(path), "error": f"no origin default branch in {repo}"}

    result = {"file": str(path), "service": service, "repo": str(repo), "ref": ref, "anchors": []}

    sha = fm_scalar(fm, "verified_sha")
    paths = fm_list(fm, "verified_paths") or []
    if sha and paths:
        result["commits_behind"] = _doc_behind(repo, sha, ref, paths)
    else:
        result["commits_behind"] = None

    block = EVIDENCE.search(text[body_at:])
    if block:
        try:
            items = json.loads(block.group(1)).get("items", [])
        except ValueError:
            return {**result, "error": "orient-evidence block is not valid JSON"}
        for item in items:
            if item.get("kind") != "code":
                continue
            status, n = check_anchor(repo, ref, item)
            result["anchors"].append({"id": item["id"], "ref": item["ref"], "status": status, "commits": n})
    result["drifted"] = [a["id"] for a in result["anchors"] if a["status"] != "ok"]
    return result


def _doc_behind(repo, sha, ref, paths):
    args = ["git", "log", "--oneline", f"{sha}..{ref}", "--"] + paths
    rc, out, _ = sh(args, cwd=repo)
    return None if rc != 0 else len([line for line in out.splitlines() if line.strip()])


def stamp(path, result):
    text = path.read_text()
    fm, body_at = split_frontmatter(text)
    updates = {
        "drifted_evidence": "[" + ", ".join(str(i) for i in result["drifted"]) + "]",
        "drift_checked": datetime.date.today().isoformat(),
    }
    if result.get("commits_behind") is not None:
        updates["commits_behind"] = str(result["commits_behind"])
    lines = fm.split("\n")
    for key, value in updates.items():
        for i, line in enumerate(lines):
            if re.match(rf"^{re.escape(key)}:", line):
                lines[i] = f"{key}: {value}"
                break
        else:
            lines.append(f"{key}: {value}")
    path.write_text("---\n" + "\n".join(lines) + "\n---\n" + text[body_at:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()

    files = [pathlib.Path(f).expanduser() for f in args.files]
    if args.all:
        files += sorted((VAULT / "Engineering").glob("*/explainers/*.md"))
    if not files:
        ap.error("give an explainer path, or --all")

    results, bad = [], False
    for f in files:
        r = check(f, fetch=not args.no_fetch)
        results.append(r)
        if "error" in r:
            bad = True
        elif args.write:
            stamp(f, r)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            name = pathlib.Path(r["file"]).name
            if "error" in r:
                print(f"{name}: ERROR {r['error']}")
                continue
            behind = r["commits_behind"]
            print(f"{name}: {len(r['drifted'])} of {len(r['anchors'])} anchors moved"
                  + (f", {behind} commit(s) behind on verified_paths" if behind is not None else "")
                  + f"  [{r['ref']}]")
            for a in r["anchors"]:
                if a["status"] != "ok":
                    extra = f" ({a['commits']} commit(s))" if a["commits"] else ""
                    print(f"  [{a['id']}] {a['status']}{extra}  {a['ref']}")
    sys.exit(2 if bad else 0)


if __name__ == "__main__":
    main()
