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
            if os.path.exists(".appveyor.yml"):
                has_appveyor_yaml = True
            else:
                has_appveyor_yaml = False

            if not has_appveyor_yaml:
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
                print("    appveyor # of builds:", len(r.json()['project']['builds']))
                print("    appveyor config:", has_appveyor_yaml)

        # did it work, commit, made API calls
        return deleted, False, True
