import os
import time

import requests
from ruamel.yaml import YAML

from .base import Migrator

MAX_PER_HOUR = 50


class DummyMeta:
    def __init__(self, meta_yaml):
        _yml = YAML(typ="jinja2")
        _yml.indent(mapping=2, sequence=4, offset=2)
        _yml.width = 160
        _yml.allow_duplicate_keys = True
        self.meta = _yml.load(meta_yaml)


class TeamsCleanup(Migrator):
    main_branch_only = True
    max_processes = 1
    continual = True

    def _should_migrate(self):
        if not hasattr(self, "_time_between"):
            # we do 50 an hour
            self._time_between = 60.0 * 60.0 / MAX_PER_HOUR

            # prevent a circular import by doing this here
            from admin_migrations.__main__ import N_WORKERS

            # if we have more than one process, that time gets longer
            self._time_between = self._time_between * N_WORKERS

        now = time.time()

        if not hasattr(self, "_time_of_last_migration"):
            self._time_of_last_migration = now
            return True

        if now - self._time_of_last_migration > self._time_between:
            self._time_of_last_migration = now
            return True

        return False

    def migrate(self, feedstock, branch):
        repo_name = "%s-feedstock" % feedstock

        team_name = feedstock.lower()
        if team_name in [
            "core",
            "bot",
            "staged-recipes",
            "arm-arch",
            "systems",
        ] or team_name.startswith("help-"):
            return

        if self._should_migrate() or "DEBUG_ADMIN_MIGRATIONS" in os.environ:
            rsp = requests.post(
                "https://conda-forge.herokuapp.com/conda-forge-teams/update",
                headers={"CF_WEBSERVICES_TOKEN": os.environ["CF_WEBSERVICES_TOKEN"]},
                json={"feedstock": repo_name},
            )
            rsp.raise_for_status()
            print("    updated team", flush=True)

            # migration done, make a commit, lots of API calls
            return False, False, True
        else:
            return False, False, False
