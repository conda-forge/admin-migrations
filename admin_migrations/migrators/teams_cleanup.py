import os
import random

import requests
from ruamel.yaml import YAML

from admin_migrations.defaults import MAX_MIGRATE

from .base import Migrator

RND = random.SystemRandom()


def _get_random_frac():
    """We do 50 per hour no matter what."""
    if MAX_MIGRATE > 0:
        frac = 50 / MAX_MIGRATE
    else:
        frac = 1

    return frac


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

        if RND.random() < _get_random_frac() or "DEBUG_ADMIN_MIGRATIONS" in os.environ:
            rsp = requests.post(
                "https://conda-forge.herokuapp.com/conda-forge-teams/update",
                headers={"CF_WEBSERVICES_TOKEN": os.environ["CF_WEBSERVICES_TOKEN"]},
                json={"feedstock": repo_name},
            )
            rsp.raise_for_status()
            print("    updated team", flush=True)

        # migration done, make a commit, lots of API calls
        return False, False, True
