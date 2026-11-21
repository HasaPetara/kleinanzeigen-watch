"""Laedt den Projektordner per GitHub-API in ein Repository.

Braucht ein Personal Access Token mit den Rechten 'repo' und 'workflow'
(Datei .github/workflows/... laesst sich sonst nicht anlegen).

    python tools/upload_to_github.py --repo Owner/name
    python tools/upload_to_github.py --repo Owner/name --dry-run
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TOKEN_FILE = PROJECT.parent / "tmp" / "github-token.txt"

SKIP_DIRS = {".git", "__pycache__", "logs", ".venv", "node_modules"}
SKIP_FILES = {"state.json", "state.json.tmp", "github-token.txt"}
SKIP_SUFFIXES = {".pyc", ".log"}


class GitHubError(Exception):
    def __init__(self, code: int, path: str, detail: str) -> None:
        super().__init__(f"GitHub-Fehler {code} bei {path}: {detail}")
        self.code = code


def api(token: str, method: str, path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "kleinanzeigen-watch-uploader",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise GitHubError(exc.code, f"{method} {path}", detail) from exc


def collect_files() -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for path in sorted(PROJECT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if relative.name in SKIP_FILES or path.suffix in SKIP_SUFFIXES:
            continue
        files.append((relative.as_posix(), path.read_bytes()))
    return files


def read_token(explicit: str | None) -> str:
    if explicit:
        return explicit.strip()
    if TOKEN_FILE.is_file():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit(f"Kein Token gefunden. Lege ihn in {TOKEN_FILE} ab.")


def current_commit(token: str, owner: str, repo: str, branch: str) -> str | None:
    try:
        ref = api(token, "GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
    except GitHubError:
        return None
    return ref.get("object", {}).get("sha")


def bootstrap(token: str, owner: str, repo: str, branch: str) -> str:
    """Erster Commit, damit die Git-Data-API benutzbar wird."""
    print("Repo ist leer - lege Start-Commit an ...")
    api(
        token,
        "PUT",
        f"/repos/{owner}/{repo}/contents/.init",
        {
            "message": "init",
            "branch": branch,
            "content": base64.b64encode(b"init").decode("ascii"),
        },
    )
    sha = current_commit(token, owner, repo, branch)
    if not sha:
        raise SystemExit("Start-Commit konnte nicht angelegt werden.")
    return sha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--message", default="kleinanzeigen-watch: Upload")
    parser.add_argument("--token", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = collect_files()
    total = sum(len(content) for _, content in files)
    print(f"{len(files)} Dateien, {total / 1024:.0f} KB")

    if args.dry_run:
        for name, content in files:
            print(f"  {len(content):>8}  {name}")
        return 0

    token = read_token(args.token)
    owner, _, repo = args.repo.partition("/")

    info = api(token, "GET", f"/repos/{owner}/{repo}")
    print(f"Repo ok: {info['full_name']} (public={not info['private']})")

    parent = current_commit(token, owner, repo, args.branch) or bootstrap(
        token, owner, repo, args.branch
    )

    tree_entries = []
    for name, content in files:
        blob = api(
            token,
            "POST",
            f"/repos/{owner}/{repo}/git/blobs",
            {"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
        )
        tree_entries.append(
            {"path": name, "mode": "100644", "type": "blob", "sha": blob["sha"]}
        )
        print(f"  blob {name}")

    tree = api(token, "POST", f"/repos/{owner}/{repo}/git/trees", {"tree": tree_entries})
    commit = api(
        token,
        "POST",
        f"/repos/{owner}/{repo}/git/commits",
        {"message": args.message, "tree": tree["sha"], "parents": [parent]},
    )
    api(
        token,
        "PATCH",
        f"/repos/{owner}/{repo}/git/refs/heads/{args.branch}",
        {"sha": commit["sha"], "force": True},
    )

    print(f"Fertig: https://github.com/{owner}/{repo}/commit/{commit['sha']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
