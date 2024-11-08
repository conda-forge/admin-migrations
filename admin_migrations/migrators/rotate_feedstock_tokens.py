import os
import random
import subprocess

import requests
from conda_smithy.ci_register import travis_get_repo_info

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


def _write_travis_token(token_env):
    smithy_conf = os.path.expanduser("~/.conda-smithy")
    if not os.path.exists(smithy_conf):
        os.mkdir(smithy_conf)

    with open(os.path.join(smithy_conf, "travis.token"), "w") as fh:
        fh.write(os.environ[token_env])


class RotateFeedstockToken(Migrator):
    main_branch_only = True
    max_processes = 1

    def migrate(self, feedstock, branch):
        if random.uniform(0, 1) < 0.5:
            _write_travis_token("TRAVIS_TOKEN_A")
        else:
            _write_travis_token("TRAVIS_TOKEN_B")

        # test to make sure travis ci api is working
        # if not skip migration
        repo_info = travis_get_repo_info("conda-forge", feedstock + "-feedstock")
        if not repo_info:
            print(
                "    travis-ci API not working - skipping migration for now",
                flush=True,
            )
            return False, False, True

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
                "--without-circle",
                "--without-drone",
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
