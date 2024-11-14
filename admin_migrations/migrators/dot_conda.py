import functools
import os
import subprocess

import github
from ruamel.yaml import YAML

from .base import Migrator


@functools.lru_cache(maxsize=1)
def _gh():
    return github.Github(os.environ["GITHUB_TOKEN"])


def _read_conda_forge_yaml(yaml):
    if os.path.exists("conda-forge.yml"):
        with open("conda-forge.yml") as fp:
            meta_yaml = fp.read()

        if (
            meta_yaml is None
            or meta_yaml.strip() == "[]"
            or meta_yaml.strip() == "[ ]"
            or len(meta_yaml) == 0
            or len(meta_yaml.strip()) == 0
        ):
            cfg = {}
        else:
            cfg = yaml.load(meta_yaml)
    else:
        meta_yaml = ""
        cfg = {}

    return cfg


class DotConda(Migrator):
    def migrate(self, feedstock, branch):
        repo = _gh().get_repo("conda-forge/%s-feedstock" % feedstock)
        if repo.archived:
            # migration done, make a commit, lots of API calls
            return True, False, False

        yaml = YAML()
        cfg = _read_conda_forge_yaml(yaml)
        if "conda_build" not in cfg or "pkg_format" not in cfg["conda_build"]:
            if "conda_build" not in cfg:
                cfg["conda_build"] = {}
            cfg["conda_build"]["pkg_format"] = "2"
            with open("conda-forge.yml", "w") as fp:
                yaml.dump(cfg, fp)
            subprocess.run(
                ["git", "add", "conda-forge.yml"],
                check=True,
            )
            print("    updated conda-forge.yml", flush=True)
            updated_cfy = True
        else:
            updated_cfy = False

        # migration done, make a commit, lots of API calls
        return True, updated_cfy, False
