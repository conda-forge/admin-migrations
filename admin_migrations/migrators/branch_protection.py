import os

import github

from .base import Migrator

GH = github.Github(os.environ['GITHUB_TOKEN'])
ORG = GH.get_organization("conda-forge")


class BranchProtection(Migrator):
    main_branch_only = True
    max_processes = 1

    def migrate(self, feedstock, branch):
        repo_name = "%s-feedstock" % feedstock

        gh_repo = ORG.get_repo(repo_name)
        branch = gh_repo.get_branch("main")
        try:
            branch.edit_protection(
                enforce_admins=True,
                allow_force_pushes=False,
                allow_deletions=False,
            )
            migration_done = True
        except Exception:
            migration_done = False

        # migration done, make a commit, lots of API calls
        return migration_done, False, True
