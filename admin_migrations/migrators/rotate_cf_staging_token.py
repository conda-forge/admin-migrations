import subprocess

from .base import Migrator


class RotateCFStagingToken(Migrator):
    main_branch_only = True

    def migrate(self, feedstock, branch):
        subprocess.run(
            "conda smithy update-binstar-token "
            "--without-appveyor --without-azure "
            "--token_name STAGING_BINSTAR_TOKEN",
            shell=True,
            check=True
        )
        print("    rotated staging binstar token", flush=True)

        # migration done, make a commit, lots of API calls
        return True, False, True
