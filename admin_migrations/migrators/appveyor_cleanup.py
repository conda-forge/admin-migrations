import os
import subprocess

import requests
from ruamel.yaml import YAML

from .base import Migrator

YAML = YAML()


def _get_num_builds(appveyor_name):
    headers = {"Authorization": "Bearer " + os.environ["APPVEYOR_TOKEN"]}

    r = requests.get(
        "https://ci.appveyor.com/api/projects/conda-forge/"
        "%s/history?recordsNumber=10" % appveyor_name,
        headers=headers,
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


def _has_appveyor_any_branch(curr_branch):
    o = subprocess.run(
        ["git", "branch", "-r"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    branches = []
    for line in o.stdout.decode("utf-8").split("\n"):
        if len(line) > 0 and "origin/HEAD" not in line:
            branches.append(line.strip()[len("origin/") :])

    _has_app = []
    for branch in branches:
        subprocess.run(["git", "checkout", branch], check=True)
        with open("conda-forge.yml") as fp:
            cf_cfg = YAML.load(fp)

        if cf_cfg.get("provider", {}).get("win", None) == "azure":
            _has_app.append(False)
        else:
            _has_app.append(any(os.path.exists(cfg) for cfg in CFGS))

    subprocess.run(["git", "checkout", curr_branch], check=True)
    return any(_has_app)


class AppveyorDelete(Migrator):
    # we need to check each branch, but this migrator should only be called
    # once per feedstock on the main branch
    main_branch_only = False
    max_workers = 1

    def migrate(self, feedstock, branch):
        headers = {"Authorization": "Bearer " + os.environ["APPVEYOR_TOKEN"]}

        assert branch == "main" or branch == "master"
        deleted = False

        appveyor_name = "%s-feedstock" % feedstock
        if appveyor_name.startswith("_"):
            appveyor_name = appveyor_name[1:]
        appveyor_name = appveyor_name.replace("_", "-").replace(".", "-")

        r = requests.get(
            "https://ci.appveyor.com/api/projects/conda-forge/%s" % appveyor_name,
            headers=headers,
        )

        if r.status_code == 404:
            print("    appveyor project not found", flush=True)
            # project does not exist
            deleted = True
        elif r.status_code == 200:
            has_appveyor = _has_appveyor_any_branch(branch)
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
            #         headers=headers,
            #     )
            #
            #     if r.status_code == 204:
            #         print("    appveyor project deleted", flush=True)
            #         deleted = True
            #     else:
            #         print("    appveyor delete call failed", flush=True)
            # el
            if not has_appveyor:
                r = requests.get(
                    "https://ci.appveyor.com/api/projects/"
                    "conda-forge/%s/settings" % appveyor_name,
                    headers=headers,
                )
                if r.status_code == 200:
                    settings = r.json()["settings"]
                    settings["disablePushWebhooks"] = True
                    r = requests.put(
                        "https://ci.appveyor.com/api/projects",
                        headers=headers,
                        json=settings,
                    )
                    if r.status_code == 204:
                        print("    appveyor disabled pushes", flush=True)
                        deleted = True
                    else:
                        print("    appveyor disable push call failed", flush=True)
                else:
                    print("    appveyor get project settings failed", flush=True)
            else:
                print("    appveyor # of builds:", num_builds, flush=True)
                print("    appveyor on:", has_appveyor, flush=True)

        # did it work, commit, made API calls
        return deleted, False, True


class AppveyorForceDelete(Migrator):
    main_branch_only = True

    def migrate(self, feedstock, branch):
        headers = {"Authorization": "Bearer " + os.environ["APPVEYOR_TOKEN"]}

        if feedstock == "python":
            return True, False, False
        else:
            deleted = False

            appveyor_name = "%s-feedstock" % feedstock
            if appveyor_name.startswith("_"):
                appveyor_name = appveyor_name[1:]
            appveyor_name = appveyor_name.replace("_", "-").replace(".", "-")

            r = requests.get(
                "https://ci.appveyor.com/api/projects/conda-forge/%s" % appveyor_name,
                headers=headers,
            )

            if r.status_code == 404:
                print("    appveyor project not found", flush=True)
                # project does not exist
                deleted = True
            elif r.status_code == 200:
                r = requests.get(
                    "https://ci.appveyor.com/api/projects/"
                    "conda-forge/%s/settings" % appveyor_name,
                    headers=headers,
                )
                if r.status_code == 200:
                    settings = r.json()["settings"]
                    settings["disablePushWebhooks"] = True
                    r = requests.put(
                        "https://ci.appveyor.com/api/projects",
                        headers=headers,
                        json=settings,
                    )
                    if r.status_code == 204:
                        print("    appveyor disabled pushes", flush=True)
                        deleted = True
                    else:
                        print("    appveyor disable push call failed", flush=True)
                else:
                    print("    appveyor get project settings failed", flush=True)

            # did it work, commit, made API calls
            return deleted, False, True
