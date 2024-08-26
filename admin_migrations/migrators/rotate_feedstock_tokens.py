import os
import requests
import subprocess
import github
import random

from conda_smithy.ci_register import travis_get_repo_info

from .base import Migrator

SMITHY_CONF = os.path.expanduser("~/.conda-smithy")
FEEDSTOCK_TOKENS_REPO = github.Github(os.environ["GITHUB_TOKEN"]).get_repo(
    "conda-forge/feedstock-tokens"
)


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


def _delete_feedstock_token(feedstock_name):
    token_file = "tokens/%s.json" % feedstock_name
    fn = FEEDSTOCK_TOKENS_REPO.get_contents(token_file)
    FEEDSTOCK_TOKENS_REPO.delete_file(
        token_file,
        "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** removing "
        "token for %s" % feedstock_name,
        fn.sha,
    )


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

        # delete the old token
        if _feedstock_token_exists(feedstock + "-feedstock"):
            _delete_feedstock_token(feedstock + "-feedstock")
            print("    deleted old feedstock token", flush=True)

        feedstock_dir = "../%s-feedstock" % feedstock
        owner_info = ["--organization", "conda-forge"]

        # make a new one
        subprocess.check_call(
            " ".join(
                [
                    "conda",
                    "smithy",
                    "generate-feedstock-token",
                    "--feedstock_directory",
                    feedstock_dir,
                ]
                + owner_info
            ),
            shell=True,
        )
        print("    created new feedstock token", flush=True)

        # register
        subprocess.check_call(
            " ".join(
                [
                    "conda",
                    "smithy",
                    "register-feedstock-token",
                    "--feedstock_directory",
                    feedstock_dir,
                    "--without-circle",
                    "--without-drone",
                    "--without-github-actions",
                ]
                + owner_info
                + [
                    "--token_repo",
                    "https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/"
                    "feedstock-tokens",
                ]
            ),
            shell=True,
        )
        print("    registered new feedstock token", flush=True)

        # migration done, make a commit, lots of API calls
        return True, False, True
