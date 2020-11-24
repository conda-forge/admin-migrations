import requests

from .base import Migrator


def _travis_reconfigure(user, project):
    from conda_smithy.ci_register import (
        travis_endpoint,
        travis_headers,
        travis_get_repo_info,
    )

    headers = travis_headers()
    repo_info = travis_get_repo_info(user, project)

    if not repo_info:
        print("    no repo info for travis-ci", flush=True)
        return False

    repo_id = repo_info["id"]

    if repo_info["active"] is not True:
        print("    repo is not active", flush=True)
        return True

    settings = [
        ("auto_cancel_pull_requests", True),
    ]
    for name, value in settings:
        url = "{}/repo/{repo_id}/setting/{name}".format(
            travis_endpoint, repo_id=repo_id, name=name
        )
        data = {"setting.value": value}
        response = requests.patch(url, json=data, headers=headers)
        if response.status_code not in [200, 204]:
            print("    response %s from request" % response.status_code, flush=True)
            return False

    return True


class TravisCIAutoCancelPRs(Migrator):
    master_branch_only = True

    def migrate(self, feedstock, branch):
        user = "conda-forge"
        project = "%s-feedstock" % feedstock

        if branch == "master":
            done = _travis_reconfigure(user, project)
            if done:
                print("    configured travis-ci", flush=True)
            else:
                print("    error in configuring travis-ci", flush=True)
        else:
            done = True

        # migration done, make a commit, lots of API calls
        return done, False, True
