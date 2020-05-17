import os
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
"""


class CondaForgeAutomerge(Migrator):
    def migrate(self, feedstock, branch):
        if (
            os.path.exists(".github/workflows/automerge.yml")
            and not os.path.exists(".github/workflows/main.yml")
        ):
            return True, False, False

        os.makedirs(".github/workflows", exist_ok=True)

        if not os.path.exists(".github/workflows/automerge.yml"):
            with open(".github/workflows/automerge.yml", "w") as fp:
                fp.write(AUTOMERGE)
            subprocess.run(
                ["git", "add", ".github/workflows/automerge.yml"],
                check=True,
            )

        if os.path.exists(".github/workflows/main.yml"):
            subprocess.run(
                ["git", "rm", "-f", ".github/workflows/main.yml"],
                check=True,
            )

        return True, True, False
