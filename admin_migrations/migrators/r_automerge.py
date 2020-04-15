import os
import subprocess

from ruamel.yaml import YAML

from .base import Migrator


def _has_r_team():
    yaml = YAML()

    with open(os.path.join("recipe", "meta.yaml"), "r") as fp:
        keep_lines = []
        skip = True
        for line in fp.readlines():
            if line.startswith("extra:"):
                skip = False
            if not skip:
                keep_lines.append(line)

    maints = yaml.load("".join(keep_lines))["extra"]["recipe-maintainers"]
    maints = [m.strip() for m in maints]
    return "conda-forge/r" in maints


def _has_cran_url():
    with open(os.path.join("recipe", "meta.yaml"), "r") as fp:
        meta_yaml = fp.read()
    return "{{ cran_mirror }}" in meta_yaml


class RAutomerge(Migrator):
    """Adds bot automerge to any feedstock that has

        1. r-* in the name
        2. has conda-forge/r on the maintainers list
        3. uses the {{ cran_mirror }} jinja2 variable
    """
    def migrate(self, feedstock, branch):
        if (
            feedstock.startswith("r-")
            and feedstock not in ["r", "r-base"]
            and _has_r_team()
            and _has_cran_url()
        ):
            with open("conda-forge.yml", "r") as fp:
                meta_yaml = fp.read()

            if meta_yaml.strip() == "[]" or meta_yaml.strip() == "[ ]":
                cfg = {}
            else:
                yaml = YAML()
                cfg = yaml.load(meta_yaml)

            cfg["bot"] = {"automerge": True}

            with open("conda-forge.yml", "w") as fp:
                yaml.dump(cfg, fp)

            subprocess.run(
                ["git", "add", "conda-forge.yml"],
                check=True,
            )

            # did migration, make a commit, no api calls
            return True, True, False
        else:
            # no migration, no commit needs to be made, no api calls
            return False, False, False
