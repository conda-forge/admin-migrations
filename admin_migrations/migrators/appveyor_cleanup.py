import os
import requests

from .base import Migrator

HEADERS = {"Authorization": "Bearer " + os.environ['APPVEYOR_TOKEN']}


class AppveyorDelete(Migrator):
    def migrate(self, feedstock):
        deleted = False

        r = requests.get(
            "https://ci.appveyor.com/api/projects/"
            "conda-forge/%s-feedstock" % feedstock,
            headers=HEADERS,
        )

        if r.status_code == 404:
            print("    appveyor project not found")
            # project does not exist
            deleted = True
        elif r.status_code == 200:
            num_builds = len(r.json()['project']['builds'])

            if num_builds == 0:
                r = requests.delete(
                    "https://ci.appveyor.com/api/projects/"
                    "conda-forge/%s-feedstock" % feedstock,
                    headers=HEADERS,
                )

                if r.status_code == 204:
                    print("    appveyor project deleted")
                    deleted = True
                else:
                    print("    appveyor delete call failed")
            else:
                print("    appveyor has %d builds" % num_builds)

        # did it work, commit, made API calls
        return deleted, False, True
