import os
import requests
import subprocess
import tempfile

from .base import Migrator

SMITHY_CONF = os.path.expanduser('~/.conda-smithy')


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
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.check_call(
            "git clone https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/"
            "feedstock-tokens.git",
            cwd=tmpdir,
            shell=True,
        )

        subprocess.check_call(
            "git remote set-url --push origin "
            "https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/"
            "feedstock-tokens.git",
            cwd=os.path.join(tmpdir, "feedstock-tokens"),
            shell=True,
        )

        subprocess.check_call(
            "git rm tokens/%s.json" % feedstock_name,
            cwd=os.path.join(tmpdir, "feedstock-tokens"),
            shell=True,
        )

        subprocess.check_call(
            "git commit --allow-empty -am "
            "'[ci skip] [skip ci] [cf admin skip] ***NO_CI*** removing "
            "token for %s'" % feedstock_name,
            cwd=os.path.join(tmpdir, "feedstock-tokens"),
            shell=True,
        )

        subprocess.check_call(
            "git pull",
            cwd=os.path.join(tmpdir, "feedstock-tokens"),
            shell=True,
        )

        subprocess.check_call(
            "git push",
            cwd=os.path.join(tmpdir, "feedstock-tokens"),
            shell=True,
        )


class RotateFeedstockToken(Migrator):
    main_branch_only = True

    def migrate(self, feedstock, branch):
        # delete the old token
        if _feedstock_token_exists(feedstock + "-feedstock"):
            _delete_feedstock_token(feedstock + "-feedstock")
            print("    deleted old feedstock token")

        feedstock_dir = "../%s-feedstock" % feedstock
        owner_info = ['--organization', 'conda-forge']

        # make a new one
        subprocess.check_call(
            " ".join(
                [
                    'conda', 'smithy', 'generate-feedstock-token',
                    '--feedstock_directory', feedstock_dir
                ]
                + owner_info
            ),
            shell=True,
        )
        print("    created new feedstock token")

        # register
        subprocess.check_call(
            " ".join(
                [
                    'conda', 'smithy',
                    'register-feedstock-token', '--feedstock_directory',
                    feedstock_dir
                ]
                + owner_info
                + [
                    '--token_repo',
                    'https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/'
                    'feedstock-tokens'
                ]
            ),
            shell=True,
        )
        print("    registered new feedstock token")

        # migration done, make a commit, lots of API calls
        return True, False, True
