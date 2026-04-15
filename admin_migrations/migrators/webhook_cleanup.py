import functools
import os

import github

from .base import Migrator


@functools.lru_cache(maxsize=1)
def _gh():
    return github.Github(auth=github.Auth.Token(os.environ["GITHUB_TOKEN"]))


class WebhookCleanup(Migrator):
    main_branch_only = True
    max_processes = 1

    def migrate(self, feedstock, branch):
        repo = _gh().get_repo(f"conda-forge/{feedstock}-feedstock")

        domains_to_check = [
            "conda-forge.herokuapp.com",
            "travis-ci.org",
            "cloud.drone.io",
            "circleci.com",
            "ci.appveyor.com",
        ]

        for hook in repo.get_hooks():
            if any(domain in hook.config["url"] for domain in domains_to_check):
                hook.delete()

        # migration done, make a commit, lots of API calls
        return True, False, True
