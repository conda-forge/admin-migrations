import os
import requests
import subprocess

from .base import Migrator

HEADERS = {"Authorization": "Bearer " + os.environ['APPVEYOR_TOKEN']}


def _get_num_builds(appveyor_name):
    r = requests.get(
        "https://ci.appveyor.com/api/projects/conda-forge/"
        "%s/history?recordsNumber=10" % appveyor_name,
        headers=HEADERS,
    )

    if r.status_code == 200:
        return len(r.json()["builds"])
    else:
        return -1


CFGS = [
    ".appveyor.yml",
    ".appveyor.yaml",
    "appveyor.yml",
    "appveyor.yaml",
]


def _has_appveyor_config_any_branch(curr_branch):
    o = subprocess.run(
        ["git", "branch", "-r"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    branches = []
    for line in o.stdout.decode("utf-8").split('\n'):
        if len(line) > 0 and "origin/HEAD" not in line:
            branches.append(line.strip()[len("origin/"):])

    _has_cfg = []
    for branch in branches:
        subprocess.run(["git", "checkout", branch], check=True)
        _has_cfg.append(any(os.path.exists(cfg) for cfg in CFGS))

    subprocess.run(["git", "checkout", curr_branch], check=True)
    return any(_has_cfg)


class AppveyorDelete(Migrator):
    # we need to check each branch, but this migrator should only be called
    # once per feedstock on the master branch
    master_branch_only = False

    def migrate(self, feedstock, branch):
        assert branch == "master"
        deleted = False

        appveyor_name = "%s-feedstock" % feedstock
        if appveyor_name.startswith("_"):
            appveyor_name = appveyor_name[1:]
        appveyor_name = appveyor_name.replace("_", "-").replace(".", "-")

        r = requests.get(
            "https://ci.appveyor.com/api/projects/"
            "conda-forge/%s" % appveyor_name,
            headers=HEADERS,
        )

        if r.status_code == 404:
            print("    appveyor project not found")
            # project does not exist
            deleted = True
        elif r.status_code == 200:
            has_any_cfg = _has_appveyor_config_any_branch(branch)
            num_builds = _get_num_builds(appveyor_name)

            # this logic catches cases where
            #   1. there are no builds
            #   2. there is only one branch and it is not built
            #
            # it will miss repos with more than one branch and builds in the
            # past, but no builds now - we will have to get these by hand
            # if num_builds == 0:
            #     r = requests.delete(
            #         "https://ci.appveyor.com/api/projects/"
            #         "conda-forge/%s" % appveyor_name,
            #         headers=HEADERS,
            #     )
            #
            #     if r.status_code == 204:
            #         print("    appveyor project deleted")
            #         deleted = True
            #     else:
            #         print("    appveyor delete call failed")
            # el
            if not has_any_cfg:
                r = requests.get(
                    "https://ci.appveyor.com/api/projects/"
                    "conda-forge/%s/settings" % appveyor_name,
                    headers=HEADERS,
                )
                if r.status_code == 200:
                    settings = r.json()["settings"]
                    settings["disablePushWebhooks"] = True
                    r = requests.put(
                        "https://ci.appveyor.com/api/projects",
                        headers=HEADERS,
                        json=settings,
                    )
                    if r.status_code == 204:
                        print("    appveyor disabled pushes")
                        deleted = True
                    else:
                        print("    appveyor disable push call failed")
                else:
                    print("    appveyor get project settings failed")
            else:
                print("    appveyor # of builds:", num_builds)
                print("    appveyor config:", has_any_cfg)

        # did it work, commit, made API calls
        return deleted, False, True
