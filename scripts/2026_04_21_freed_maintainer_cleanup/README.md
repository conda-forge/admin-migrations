# Recipe maintainer cleanup (2026-04-21)

A sweep of every conda-forge feedstock's recipe turned up 71 maintainer
logins that no longer resolve on GitHub (`GET /users/<login>` → 404)
across 103 feedstocks.

This directory holds a one-shot local cleanup: for every affected feedstock
we either

- replace the missing login with the maintainer's confirmed current login
  (where the rename could be established by cross-referencing staged-recipes
  git author metadata or PR authorship), or
- remove the missing login from the list (where no current handle could be
  recovered).

## Running

Requires `git`, Python 3.9+, and `GITHUB_TOKEN` with push access to
`conda-forge/*-feedstock` repos (i.e. conda-forge org member with
feedstock-maintainer privileges).

```bash
# dry run (prints the diff it would apply; makes no changes)
python cleanup.py

# actually commit and push
python cleanup.py --commit
```

Behaviour:

- clones each feedstock shallow to `/tmp`
- edits only the single `- <freed_login>` line in `extra.recipe-maintainers`
- commits with `[ci skip] [skip ci] [cf admin skip] ***NO_CI***` so CI is
  suppressed per admin-migrations guidelines
- pushes to the feedstock's default branch
- skips already-fixed feedstocks idempotently (so the script is resumable)
- appends each processed feedstock to `done.txt`

## Input

`mapping.tsv` — three columns: `feedstock`, `freed_login`, `new_login`.
Leave `new_login` empty to remove the freed login without replacement.

## Audit trail

Each commit is reproducible from `mapping.tsv`; the source data
(`freed.txt`, `exposed_feedstocks.tsv`, `rename_candidates.tsv`) used to
derive the mapping lives in the triage repo, not here.
