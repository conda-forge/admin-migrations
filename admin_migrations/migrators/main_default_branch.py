import subprocess
import os
from functools import lru_cache
import requests
import time

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


@lru_cache(maxsize=1)
def _get_req_session(github_token):
    # based on
    #  https://alexwlchan.net/2019/03/
    #    creating-a-github-action-to-auto-merge-pull-requests/
    # with lots of edits
    sess = requests.Session()
    sess.headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {github_token}",
        "User-Agent": f"GitHub Actions script in {__file__}"
    }

    def raise_for_status(resp, *args, **kwargs):
        try:
            resp.raise_for_status()
        except Exception as e:
            print('ERROR:', resp.text)
            raise e

    sess.hooks["response"].append(raise_for_status)

    return sess


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


def _reset_local_branch(old_def_branch):
    subprocess.run(
        "git stash && "
        f"git branch -m {old_def_branch} main && "
        "git fetch origin && "
        "git branch -u origin/main main && "
        "git remote set-head origin -a && "
        "git stash pop",
        check=True,
        shell=True,
    )


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
        if repo.default_branch != "main" and branch == repo.default_branch:
            # once pygithub 1.56 or greater is out we can use this
            # repo.rename_branch(repo.default_branch, "main")

            sess = _get_req_session(os.environ['GITHUB_TOKEN'])
            r = sess.post(
                "https://api.github.com"
                "/repos/%s/branches/%s/rename" % (repo.full_name, repo.default_branch),
                data={"new_name": "main"},
            )
            r.raise_for_status()
            time.sleep(5)
            print("    renamed branch '%s' to 'main'" % repo.default_branch, flush=True)

            # the upstream branch has changed, so need to reset local clone
            _reset_local_branch(repo.default_branch)
            print("    reset local branch to 'main'", flush=True)

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
