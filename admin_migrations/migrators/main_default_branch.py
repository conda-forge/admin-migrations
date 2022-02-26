import subprocess
import os

import github
from ruamel.yaml import YAML

from .base import Migrator

GH = github.Github(os.environ['GITHUB_TOKEN'])

AUTOMERGE_MAIN = """\
on:
  status: {}
  check_suite:
    types:
      - completed

jobs:
  automerge-action:
    runs-on: ubuntu-latest
    name: automerge
    steps:
      - name: checkout
        uses: actions/checkout@v2
      - name: automerge-action
        id: automerge-action
        uses: conda-forge/automerge-action@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          rerendering_github_token: ${{ secrets.RERENDERING_GITHUB_TOKEN }}
"""

WEBSERVICES_MAIN = """\
on: repository_dispatch

jobs:
  webservices:
    runs-on: ubuntu-latest
    name: webservices
    steps:
      - name: webservices
        id: webservices
        uses: conda-forge/webservices-dispatch-action@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          rerendering_github_token: ${{ secrets.RERENDERING_GITHUB_TOKEN }}
"""


AUTOMERGE_MASTER = """\
on:
  status: {}
  check_suite:
    types:
      - completed

jobs:
  automerge-action:
    runs-on: ubuntu-latest
    name: automerge
    steps:
      - name: checkout
        uses: actions/checkout@v2
      - name: automerge-action
        id: automerge-action
        uses: conda-forge/automerge-action@master
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          rerendering_github_token: ${{ secrets.RERENDERING_GITHUB_TOKEN }}
"""

WEBSERVICES_MASTER = """\
on: repository_dispatch

jobs:
  webservices:
    runs-on: ubuntu-latest
    name: webservices
    steps:
      - name: webservices
        id: webservices
        uses: conda-forge/webservices-dispatch-action@master
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          rerendering_github_token: ${{ secrets.RERENDERING_GITHUB_TOKEN }}
"""


def _read_conda_forge_yaml(yaml):
    if os.path.exists("conda-forge.yml"):
        with open("conda-forge.yml", "r") as fp:
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


def _update_wfl(fname, new_wfl):
    with open(fname, "r") as fp:
        wfl = fp.read()
    if "action@master" in wfl:
        with open(fname, "w") as fp:
            fp.write(new_wfl)

        subprocess.run(
            ["git", "add", fname],
            check=True,
        )
        print("    updated " + fname, flush=True)
        return True
    else:
        return False


class CondaForgeMasterToMain(Migrator):
    def migrate(self, feedstock, branch):
        repo = GH.get_repo("conda-forge/%s-feedstock" % feedstock)
        if repo.archived:
            # migration done, make a commit, lots of API calls
            return True, False, True

        # the conda-forge config gets updated every time
        updated_automerge = _update_wfl(
            ".github/workflows/automerge.yml", AUTOMERGE_MAIN,
        )
        updated_webservices = _update_wfl(
            ".github/workflows/webservices.yml", WEBSERVICES_MAIN,
        )

        yaml = YAML()
        cfg = _read_conda_forge_yaml(yaml)
        if "github" not in cfg:
            cfg["github"] = {}
        if (
            "branch_name" not in cfg["github"]
            or cfg["github"]["branch_name"] != "main"
            or "tooling_branch_name" not in cfg["github"]
            or cfg["github"]["tooling_branch_name"] != "main"
            or (
                "upload_on_branch" in cfg
                and cfg["upload_on_branch"] == "master"
            )
        ):
            cfg["github"]["branch_name"] = "main"
            cfg["github"]["tooling_branch_name"] = "main"

            if "upload_on_branch" in cfg and cfg["upload_on_branch"] == "master":
                cfg["upload_on_branch"] = "main"

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

        make_commit = updated_automerge or updated_webservices or updated_cfy

        # only call branch rename once on current "master" branch if it exists
        if repo.default_branch != "main" and branch == "master":
            repo.rename_branch(repo.default_branch, "main")
            print("    renamed branch '%s' to 'main'" % repo.default_branch, flush=True)

        # migration done, make a commit, lots of API calls
        return True, make_commit, True


class CondaForgeGHAWithMain(Migrator):
    def migrate(self, feedstock, branch):
        with open(".github/workflows/automerge.yml", "w") as fp:
            fp.write(AUTOMERGE_MASTER)

        with open(".github/workflows/webservices.yml", "w") as fp:
            fp.write(WEBSERVICES_MASTER)

        res = subprocess.run("git diff", shell=True, check=True, capture_output=True)
        if len(res.stdout + res.stderr) > 0:
            subprocess.run(
                ["git", "add", ".github/workflows/automerge.yml"],
                check=True,
            )
            subprocess.run(
                ["git", "add", ".github/workflows/webservices.yml"],
                check=True,
            )

            # migration done, make a commit, lots of API calls
            return True, True, False
        else:
            return True, False, False
