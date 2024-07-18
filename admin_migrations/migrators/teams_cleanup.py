import os

import github
from conda_smithy.github import configure_github_team
from ruamel.yaml import YAML

from .base import Migrator

GH = github.Github(os.environ['GITHUB_TOKEN'])
ORG = GH.get_organization("conda-forge")


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

        team_name = repo_name.replace("-feedstock", "").lower()
        if (
            team_name in ["core", "bot", "staged-recipes", "arm-arch", "systems"]
            or team_name.startswith("help-")
        ):
            return

        gh_repo = ORG.get_repo(repo_name)

        keep_lines = []
        skip = True
        has_meta_yaml = False
        # First check for `meta.yaml`
        with open("recipe/meta.yaml", "r") as fp:
            has_meta_yaml = True
            for line in fp.readlines():
                if line.startswith("extra:"):
                    skip = False
                if not skip:
                    keep_lines.append(line)

        # Check for recipe.yaml instead
        if not has_meta_yaml:
            # Because `rattler_build` recipes are valid yaml
            # we can just use the whole file
            with open("recipe/recipe.yaml") as fp:
                keep_lines = fp.readlines()
        meta = DummyMeta("".join(keep_lines))
        (
            current_maintainers,
            prev_maintainers,
            new_conda_forge_members,
        ) = configure_github_team(
            meta,
            gh_repo,
            ORG,
            repo_name.replace("-feedstock", ""),
            remove=True,
        )

        # migration done, make a commit, lots of API calls
        return True, False, True
