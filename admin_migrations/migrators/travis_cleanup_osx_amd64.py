import os

from ruamel.yaml import YAML

from .base import Migrator


class TraviCINoOSXAMD64(Migrator):
    def migrate(self, feedstock, branch):
        commit = False
        if os.path.exists(".travis.yml"):
            yaml = YAML()

            with open(".travis.yml") as fp:
                cfg = yaml.load(fp.read())

            if "matrix" in cfg and "include" in cfg["matrix"]:
                changed = False
                new_entries = []
                for entry in cfg["matrix"]["include"]:
                    if entry["os"] == "osx" or entry["arch"] == "amd64":
                        changed = True
                        continue
                    else:
                        new_entries.append(entry)

                if changed:
                    cfg["matrix"]["include"] = new_entries

                    with open(".travis.yml", "w") as fp:
                        yaml.dump(cfg, fp)

                    commit = True

        # migration done, make a commit, lots of API calls
        return True, commit, False
