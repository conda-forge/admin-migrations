import os
import random

import github
from ruamel.yaml import YAML

from .base import Migrator
from ..defaults import MAX_MIGRATE

GH = github.Github(os.environ['GITHUB_TOKEN'])
ORG = GH.get_organization("conda-forge")


def _get_random_frac():
    """We do 50 per hour no matter what."""
    if MAX_MIGRATE > 0:
        frac = 50 / MAX_MIGRATE
    else:
        frac = 1

    return frac


class DummyMeta(object):
    def __init__(self, meta_yaml):
        _yml = YAML(typ='jinja2')
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
        if (
            team_name in ["core", "bot", "staged-recipes", "arm-arch", "systems"]
            or team_name.startswith("help-")
        ):
            return

        gh_repo = ORG.get_repo(repo_name)

        if (
            random.random() < _get_random_frac()
            or "DEBUG_ADMIN_MIGRATIONS" in os.environ
        ):
            gh_repo.create_issue(title="@conda-forge-admin, please update team")

        # migration done, make a commit, lots of API calls
        return False, False, True
