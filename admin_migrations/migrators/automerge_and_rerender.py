import os
import subprocess

from .base import Migrator

MAIN = """\
on:
  status: {}
  check_suite:
    types:
      - completed

jobs:
  regro-cf-autotick-bot-action:
    runs-on: ubuntu-latest
    name: regro-cf-autotick-bot-action
    steps:
      - name: checkout
        uses: actions/checkout@v2
      - name: regro-cf-autotick-bot-action
        id: regro-cf-autotick-bot-action
        uses: regro/cf-autotick-bot-action@master
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
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
"""


class AutomergeAndRerender(Migrator):
    def migrate(self, feedstock, branch):
        if (
            os.path.exists(".github/workflows/main.yml") and
            os.path.exists(".github/workflows/webservices.yml")
        ):
            return True, False, False

        os.makedirs(".github/workflows", exist_ok=True)

        if not os.path.exists(".github/workflows/main.yml"):
            with open(".github/workflows/main.yml", "w") as fp:
                fp.write(MAIN)
            subprocess.run(
                ["git", "add", ".github/workflows/main.yml"],
                check=True,
            )

        if not os.path.exists(".github/workflows/webservices.yml"):
            with open(".github/workflows/webservices.yml", "w") as fp:
                fp.write(WEBSERVICES)
            subprocess.run(
                ["git", "add", ".github/workflows/webservices.yml"],
                check=True,
            )

        return True, True, False
