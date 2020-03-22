import os
import requests
import subprocess

from .base import Migrator

HEADERS = {"Authorization": "Bearer " + os.environ['APPVEYOR_TOKEN']}


def _get_num_branches():
    o = subprocess.run(
        ["git", "branch", "-r"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    num_branches = 0
    for line in o.stdout.decode("utf-8").split('\n'):
        if len(line) > 0 and "origin/HEAD" not in line:
            num_branches += 1
    return num_branches


class AppveyorDelete(Migrator):
    def migrate(self, feedstock):
        deleted = False

        appveyor_name = "%s-feedstock" % feedstock
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
            if os.path.exists(".appveyor.yml"):
                has_appveyor_yaml = True
            else:
                has_appveyor_yaml = False

            num_branches = _get_num_branches()
            num_builds = len(r.json()['project']['builds'])

            # this logic catches cases where
            #   1. there are no builds
            #   2. there is only one branch and it is not built
            #
            # it will miss repos with more than one branch and builds in the
            # past, but no builds now - we will have to get these by hand
            if ((not has_appveyor_yaml) and num_branches == 1) or num_builds == 0:
                r = requests.delete(
                    "https://ci.appveyor.com/api/projects/"
                    "conda-forge/%s" % appveyor_name,
                    headers=HEADERS,
                )

                if r.status_code == 204:
                    print("    appveyor project deleted")
                    deleted = True
                else:
                    print("    appveyor delete call failed")
            else:
                print("    git # of branches:", num_branches)
                print("    appveyor # of builds:", num_builds)
                print("    appveyor config:", has_appveyor_yaml)

        # did it work, commit, made API calls
        return deleted, False, True
