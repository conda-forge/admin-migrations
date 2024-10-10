import os

import github

from .base import Migrator

GH = github.Github(os.environ["GITHUB_TOKEN"])
ORG = GH.get_organization("conda-forge")


def _add_branch_protection_ruleset(gh_repo):
    # setup branch protections ruleset
    # default branch may not exist yet
    ruleset_name = "conda-forge-branch-protection"

    # first, check if the ruleset exists already
    rulesets_url = gh_repo.url + "/rulesets"
    _, ruleset_list = gh_repo._requester.requestJsonAndCheck("GET", rulesets_url)
    ruleset_id = None
    for ruleset in ruleset_list:
        if ruleset["name"] == ruleset_name:
            ruleset_id = ruleset["id"]
            break

    if ruleset_id is not None:
        # update ruleset
        method = "PUT"
        url = f"{rulesets_url}/{ruleset_id}"
    else:
        # new ruleset
        method = "POST"
        url = rulesets_url

    gh_repo._requester.requestJsonAndCheck(
        method,
        url,
        input={
            "name": ruleset_name,
            "target": "branch",
            "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
            "enforcement": "active",
        },
    )


class BranchProtection(Migrator):
    main_branch_only = True
    max_processes = 1

    def migrate(self, feedstock, branch):
        repo_name = "%s-feedstock" % feedstock

        gh_repo = ORG.get_repo(repo_name)
        try:
            _add_branch_protection_ruleset(gh_repo)
            migration_done = True
        except Exception:
            migration_done = False

        # migration done, make a commit, lots of API calls
        return migration_done, False, True
