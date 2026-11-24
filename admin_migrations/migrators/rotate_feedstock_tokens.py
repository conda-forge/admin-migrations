import os
import random
import subprocess

import requests

from .base import Migrator

SMITHY_CONF = os.path.expanduser("~/.conda-smithy")


def _feedstock_token_exists(name):
    r = requests.get(
        "https://api.github.com/repos/conda-forge/"
        "feedstock-tokens/contents/tokens/%s.json" % (name),
        headers={"Authorization": "token %s" % os.environ["GITHUB_TOKEN"]},
    )
    if r.status_code != 200:
        return False
    else:
        return True


class RotateFeedstockTokenV2(Migrator):
    main_branch_only = True
    max_processes = 1
    max_migrate = 200

    def migrate(self, feedstock, branch):
        feedstock_dir = "../%s-feedstock" % feedstock
        owner_info = ["--organization", "conda-forge"]

        # make a new one
        subprocess.check_call(
            [
                "conda",
                "smithy",
                "generate-feedstock-token",
                "--unique-token-per-provider",
                "--feedstock_directory",
                "--without-all",
                "--with-azure",
                "--with-github-actions",
                feedstock_dir,
            ]
            + owner_info
        )
        print("    created new feedstock token", flush=True)

        # register
        subprocess.check_call(
            [
                "conda",
                "smithy",
                "register-feedstock-token",
                "--unique-token-per-provider",
                "--existing-tokens-time-to-expiration",
                str(int(6.5 * 60 * 60)),  # 6.5 hours
                "--feedstock_directory",
                feedstock_dir,
            ]
            + owner_info
            + [
                "--token_repo",
                "https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/"
                "feedstock-tokens",
            ]
        )
        print("    registered new feedstock token", flush=True)

        # migration done, make a commit, lots of API calls
        return True, False, True
