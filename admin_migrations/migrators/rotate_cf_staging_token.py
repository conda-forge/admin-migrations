import os
import random
import subprocess

from conda_smithy.ci_register import travis_get_repo_info

from .base import Migrator


def _write_travis_token(token_env):
    smithy_conf = os.path.expanduser("~/.conda-smithy")
    if not os.path.exists(smithy_conf):
        os.mkdir(smithy_conf)

    with open(os.path.join(smithy_conf, "travis.token"), "w") as fh:
        fh.write(os.environ[token_env])


class RotateCFStagingToken(Migrator):
    main_branch_only = True
    max_workers = 1
    max_migrate = 200

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

        subprocess.run(
            "conda smithy update-binstar-token "
            "--without-appveyor --without-azure "
            "--without-circle --without-drone "
            "--without-github-actions "
            "--token_name STAGING_BINSTAR_TOKEN",
            shell=True,
            check=True,
        )
        print("    rotated staging binstar token", flush=True)

        # migration done, make a commit, lots of API calls
        return True, False, True
