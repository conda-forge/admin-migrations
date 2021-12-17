import subprocess

from .base import Migrator

AUTOMERGE = """\
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

WEBSERVICES = """\
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


class CondaForgeGHAWithMain(Migrator):
    def migrate(self, feedstock, branch):
        with open(".github/workflows/automerge.yml", "w") as fp:
            fp.write(AUTOMERGE)

        with open(".github/workflows/webservices.yml", "w") as fp:
            fp.write(WEBSERVICES)

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
