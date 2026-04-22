#!/usr/bin/env python3
"""Replace or remove freed maintainer logins in conda-forge feedstocks.

Input: mapping.tsv with columns feedstock, freed_login, new_login (empty = remove).
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAPPING = HERE / "mapping.tsv"
DONE = HERE / "done.txt"
COMMIT_MESSAGE = (
    "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** update recipe-maintainers"
)
RECIPE_CANDIDATES = ("recipe/meta.yaml", "recipe/recipe.yaml")
DELAY_SECONDS = 3


def run(
    cmd: list[str], cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(
            f"cmd failed: {' '.join(cmd)}\nstdout: {r.stdout}\nstderr: {r.stderr}"
        )
    return r


def find_recipe(repo: Path) -> Path | None:
    for rel in RECIPE_CANDIDATES:
        p = repo / rel
        if p.exists():
            return p
    return None


def edit_recipe(text: str, freed: str, new_login: str) -> tuple[str, bool]:
    """Replace or remove a single maintainer line. Returns (new_text, changed)."""
    # Match the specific bullet in the recipe-maintainers list. The regex
    # requires we are inside the recipe-maintainers block (look-behind across
    # a few lines) and matches the single target login line, preserving any
    # surrounding list items.
    pat = re.compile(
        r"""(?P<prefix>^[ \t]+recipe[-_]maintainers:[^\n]*\n
            (?:[ \t]+-[ \t]*[^\n]*\n|[ \t]*\n)*?)
            (?P<line>[ \t]+-[ \t]*["']?"""
        + re.escape(freed)
        + r"""["']?[ \t]*(?:\#[^\n]*)?\n)""",
        re.MULTILINE | re.VERBOSE,
    )
    m = pat.search(text)
    if not m:
        return text, False

    if new_login:
        # Preserve indentation and any trailing comment pattern by replacing
        # only the login token; simpler to rewrite the whole line.
        indent = re.match(r"^[ \t]+-[ \t]*", m.group("line")).group(0)
        replacement = f"{indent}{new_login}\n"
    else:
        replacement = ""

    new_text = text[: m.start("line")] + replacement + text[m.end("line") :]
    return new_text, True


def ensure_repo_clone(feedstock: str, token: str, workdir: Path) -> Path:
    url = f"https://x-access-token:{token}@github.com/conda-forge/{feedstock}.git"
    dest = workdir / feedstock
    run(["git", "clone", "--depth=1", "--quiet", url, str(dest)])
    return dest


def default_branch(repo: Path) -> str:
    r = run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo)
    return r.stdout.strip()


def already_done(feedstock: str, freed: str) -> bool:
    if not DONE.exists():
        return False
    for line in DONE.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == feedstock and parts[1] == freed:
            return True
    return False


def record_done(feedstock: str, freed: str, result: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with DONE.open("a") as f:
        f.write(f"{feedstock}\t{freed}\t{result}\t{ts}\n")


def process_one(row: dict, token: str, commit: bool, workdir: Path) -> str:
    feedstock = row["feedstock"]
    freed = row["freed_login"]
    new_login = row.get("new_login", "").strip()

    repo = ensure_repo_clone(feedstock, token, workdir)
    recipe = find_recipe(repo)
    if recipe is None:
        return "no_recipe"

    text = recipe.read_text(encoding="utf-8")
    new_text, changed = edit_recipe(text, freed, new_login)
    if not changed:
        return "already_clean"

    recipe.write_text(new_text, encoding="utf-8")

    diff = run(["git", "diff", "--", str(recipe.relative_to(repo))], cwd=repo).stdout
    print(diff)

    if not commit:
        return "dry_run"

    # sanity: the diff must touch exactly one line in the recipe
    added = sum(
        1
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    removed = sum(
        1
        for line in diff.splitlines()
        if line.startswith("-") and not line.startswith("---")
    )
    expected = (1, 1) if new_login else (0, 1)
    if (added, removed) != expected:
        return f"unexpected_diff(+{added}/-{removed})"

    run(["git", "add", str(recipe.relative_to(repo))], cwd=repo)
    run(
        [
            "git",
            "-c",
            "user.email=conda-forge-admin@conda-forge.org",
            "-c",
            "user.name=conda-forge-admin",
            "commit",
            "-m",
            COMMIT_MESSAGE,
        ],
        cwd=repo,
    )

    branch = default_branch(repo)
    run(["git", "push", "origin", branch], cwd=repo)
    return "pushed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="actually commit and push")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", default=None, help="process only this feedstock slug")
    args = ap.parse_args()

    token = (
        os.environ.get("GITHUB_TOKEN")
        or subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True
        ).stdout.strip()
    )
    if not token:
        print("need GITHUB_TOKEN or `gh auth login`", file=sys.stderr)
        return 2

    if not MAPPING.exists():
        print(f"missing {MAPPING}", file=sys.stderr)
        return 2

    rows: list[dict] = []
    with MAPPING.open() as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if args.only and row["feedstock"] != args.only:
                continue
            rows.append(row)

    if args.limit:
        rows = rows[: args.limit]

    with tempfile.TemporaryDirectory(prefix="freed-maint-") as tmp:
        workdir = Path(tmp)
        counts: dict[str, int] = {}
        for i, row in enumerate(rows, 1):
            feedstock = row["feedstock"]
            freed = row["freed_login"]
            new = row.get("new_login", "").strip()
            action = "remove" if not new else f"rename→{new}"
            print(f"\n[{i}/{len(rows)}] {feedstock}  {freed} ({action})")

            if already_done(feedstock, freed):
                print("  already done, skipping")
                counts["already_done"] = counts.get("already_done", 0) + 1
                continue

            try:
                result = process_one(row, token, args.commit, workdir)
            except Exception as e:
                result = f"error:{type(e).__name__}:{e}"
                print(f"  {result}")

            counts[result] = counts.get(result, 0) + 1
            if args.commit:
                record_done(feedstock, freed, result)

            # rate limit after successful push
            if result == "pushed" and i < len(rows):
                time.sleep(DELAY_SECONDS)

            # tidy the clone
            slug_dir = workdir / feedstock
            if slug_dir.exists():
                shutil.rmtree(slug_dir, ignore_errors=True)

    print("\nsummary:")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
