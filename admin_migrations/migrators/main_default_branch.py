import functools
import os
import subprocess
import time
from functools import lru_cache

import github
import requests
from ruamel.yaml import YAML

from .base import Migrator

CIRCLECI_BLANK = """
# This file was generated automatically from conda-smithy. To update this configuration,
# update the conda-forge.yml and/or the recipe/meta.yaml.
# -*- mode: yaml -*-

version: 2

jobs:
  build:
    working_directory: ~/test
    machine: true
    steps:
      - run:
          # The Circle-CI build should not be active, but if this is not true for some reason, do a fast finish.
          command: exit 0

workflows:
  version: 2
  build_and_test:
    jobs:
      - build:
          filters:
            branches:
              ignore:
                - /.*/
"""  # noqa

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


@functools.lru_cache(maxsize=1)
def _gh():
    return github.Github(os.environ["GITHUB_TOKEN"])


def _run_git_command(args, check=True):
    s = subprocess.run(
        ["git"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )
    if s.returncode != 0:
        print(f"    ERROR: {s.stdout.decode('utf-8')}", flush=True)

    return s.returncode == 0, s.stdout.decode("utf-8")


def _commit_repo(msg):
    _run_git_command(
        [
            "commit",
            "--allow-empty",
            "-am",
            "[ci skip] [skip ci] [cf admin skip] " "***NO_CI*** %s" % msg,
        ]
    )


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
        "User-Agent": f"GitHub Actions script in {__file__}",
    }

    def raise_for_status(resp, *args, **kwargs):
        try:
            resp.raise_for_status()
        except Exception as e:
            print("ERROR:", resp.text)
            raise e

    sess.hooks["response"].append(raise_for_status)

    return sess


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


def _update_wfl(fname, new_wfl):
    with open(fname) as fp:
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


def _get_curr_sha():
    o = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return o.stdout.decode("utf=8").strip()


def _reset_local_branch(old_def_branch):
    s = subprocess.run(
        f"git branch -m {old_def_branch} main && "
        "git fetch origin && "
        "git branch -u origin/main main && "
        "git remote set-head origin -a ",
        check=True,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if s.returncode != 0:
        print(f"    ERROR: {s.stdout.decode('utf-8')}", flush=True)


def _master_to_main(repo):
    old_sha = _get_curr_sha()
    try:
        if os.path.exists("azure-pipelines.yml"):
            _run_git_command(
                [
                    "mv",
                    "azure-pipelines.yml",
                    "azure-pipelines.yml.bak",
                ]
            )

        if os.path.exists(".travis.yml"):
            _run_git_command(
                [
                    "mv",
                    ".travis.yml",
                    ".travis.yml.bak",
                ]
            )

        if os.path.exists(".circleci/config.yml"):
            with open(".circleci/config.yml", "w") as fp:
                fp.write(CIRCLECI_BLANK)

        _commit_repo("turning off CI for master to main migration")
        print("    turned off CI for master to main migration", flush=True)
    except Exception as e:
        print(f"    ERROR: {e!r}", flush=True)
        print(
            "    turning off CI for master to main migration FAILED on commit!",
            flush=True,
        )
        _run_git_command(["reset", "--hard", old_sha])
        return False

    try:
        _run_git_command(["push", "--quiet"])
    except Exception as e:
        print(f"    ERROR: {e!r}", flush=True)
        print(
            "    turning off CI for master to main migration FAILED on push!",
            flush=True,
        )
        _run_git_command(["reset", "--hard", old_sha])
        return False

    # wait a bit to rate-limit requests to our heroku server
    time.sleep(1)

    rev_sha = _get_curr_sha()
    worked = False
    try:
        # once pygithub 1.56 or greater is out we can use this
        # repo.rename_branch(repo.default_branch, "main")
        sess = _get_req_session(os.environ["GITHUB_TOKEN"])
        r = sess.post(
            "https://api.github.com"
            "/repos/%s/branches/%s/rename" % (repo.full_name, repo.default_branch),
            json={"new_name": "main"},
        )
        r.raise_for_status()
    except Exception as e:
        print(f"    ERROR: {e!r}", flush=True)
        print("    master to main rename FAILED in the API!", flush=True)
        worked = False
    else:
        time.sleep(5)
        print("    renamed branch '%s' to 'main'" % repo.default_branch, flush=True)

        # the upstream branch has changed, so need to reset local clone
        _reset_local_branch(repo.default_branch)
        print("    reset local branch to 'main'", flush=True)
        worked = True
    finally:
        _run_git_command(["revert", "-n", rev_sha])
        _commit_repo("turning on CI for master to main migration")
        _run_git_command(["push", "--quiet"])
        print("    turned CI back on for master to main migration", flush=True)

    # wait a bit to rate-limit requests to our heroku server
    time.sleep(1)

    return worked


class CondaForgeMasterToMain(Migrator):
    def migrate(self, feedstock, branch):
        repo = _gh().get_repo("conda-forge/%s-feedstock" % feedstock)
        if repo.archived:
            # migration done, make a commit, lots of API calls
            return True, False, False

        # only call branch rename once on current "master" branch if it exists
        if repo.default_branch != "main" and branch == repo.default_branch:
            did_master_to_main = _master_to_main(repo)
            did_api_calls = True
        else:
            did_master_to_main = False
            did_api_calls = False

        make_commit = False

        if did_master_to_main:
            # the conda-forge config gets updated every time
            updated_automerge = _update_wfl(
                ".github/workflows/automerge.yml",
                AUTOMERGE_MAIN,
            )
            updated_webservices = _update_wfl(
                ".github/workflows/webservices.yml",
                WEBSERVICES_MAIN,
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
                or ("upload_on_branch" in cfg and cfg["upload_on_branch"] == "master")
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

        # migration done, make a commit, lots of API calls
        return did_master_to_main, make_commit, did_api_calls


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
