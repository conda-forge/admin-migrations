import os
import subprocess

import github

from .base import Migrator

GH = github.Github(os.environ["GITHUB_TOKEN"])
ORG = GH.get_organization("conda-forge")


class RemoveAutomergeAndRerender(Migrator):
    def migrate(self, feedstock, branch):
        make_commit = False
        if os.path.exists(".github/workflows/automerge.yml") or os.path.exists(
            ".github/workflows/webservices.yml"
        ):
            for fname in [
                ".github/workflows/automerge.yml",
                ".github/workflows/webservices.yml",
            ]:
                if os.path.exists(fname):
                    subprocess.run(
                        ["git", "rm", "-f", fname],
                        check=True,
                    )
                    make_commit = True

        # repo_name = "%s-feedstock" % feedstock
        # gh_repo = ORG.get_repo(repo_name)
        # for fname in ["automerge.yml", "webservices.yml"]:
        #     workflow = gh_repo.get_workflow(fname)
        #     # /repos/OWNER/REPO/actions/workflows/WORKFLOW_ID/disable
        #     url = gh_repo.url + f"/actions/workflows/{workflow.id}/disable"
        #     try:
        #         gh_repo._requester.requestJsonAndCheck(
        #             "PUT",
        #             url,
        #         )
        #     except github.GithubException:
        #         pass

        # did it work, commit, made API calls
        return True, make_commit, False
