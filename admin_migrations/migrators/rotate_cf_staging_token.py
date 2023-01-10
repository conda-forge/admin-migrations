import subprocess

from conda_smithy.ci_register import travis_get_repo_info

from .base import Migrator


class RotateCFStagingToken(Migrator):
    main_branch_only = True
    max_workers = 1

    def migrate(self, feedstock, branch):
        # test to make sure travis ci api is working
        # if not skip migration
        repo_info = travis_get_repo_info("conda-forge", feedstock+"-feedstock")
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
            check=True
        )
        print("    rotated staging binstar token", flush=True)

        # migration done, make a commit, lots of API calls
        return True, False, True
