import json
import subprocess
from itertools import chain
from pathlib import Path

from .base import Migrator

DUMMY_WORKFLOW = """\
# This file was added automatically by admin-migrations. Do not modify.
# It ensures that Github Actions can run once rerendered for the first time.
# -*- mode: yaml -*-

name: Build conda package
on:
  workflow_dispatch:

jobs:
  build:
    name: Disabled build
    runs-on: ubuntu-slim
    if: false
    steps:
    - run: exit 0
"""


class EnableGHAWorkflows(Migrator):
    main_branch_only = True

    def migrate(self, feedstock, branch):
        workflows_dir = Path(".github/workflows")
        if list(chain(workflows_dir.glob("*.yml"), workflows_dir.glob("*.yaml"))):
            # Already enabled
            return True, False, False

        workflows_dir.mkdir(parents=True, exist_ok=True)

        conda_build_yml = workflows_dir / "conda-build.yml"
        if not conda_build_yml.exists():
            conda_build_yml.write_text(DUMMY_WORKFLOW)
            subprocess.run(
                ["git", "add", "-f", ".github/workflows/conda-build.yml"],
                check=True,
            )

        return True, True, False

    def skip(self, feedstock, branch):
        if super().skip(feedstock, branch):
            return True
        if feedstock not in self.feedstocks_to_process:
            return True

    @property
    def feedstocks_to_process(self):
        if not getattr(self, "_feedstocks_to_process", None):
            here = Path(__file__).parent
            json_path = here / "../../data/feedstocks_20241010-20260312.json"
            self._feedstocks_to_process = set(json.loads(json_path.read_text()))
        return self._feedstocks_to_process
