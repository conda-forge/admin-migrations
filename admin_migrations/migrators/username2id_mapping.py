import functools
import json
import os
import re
import subprocess

import github
from ruamel.yaml import YAML

from .base import Migrator

UNAME2ID_FILE = ".recipe_maintainers.json"
JINJA_PAT = re.compile(r"\{\{([^\{\}]*)\}\}")


@functools.lru_cache(maxsize=1)
def _gh():
    return github.Github(auth=github.Auth.Token(os.environ["GITHUB_TOKEN"]))


def _jinja2_repl(match):
    return "${{" + match.group(1) + "}}"


def _filter_jinja2(line):
    return JINJA_PAT.sub(_jinja2_repl, line)


class DummyMeta:
    def __init__(self, meta_yaml):
        parse_yml = YAML(typ="safe")
        parse_yml.indent(mapping=2, sequence=4, offset=2)
        parse_yml.width = 160
        parse_yml.allow_duplicate_keys = True
        self.meta = parse_yml.load(meta_yaml)


def _get_recipe_contents():
    if os.path.exists("recipe/meta.yaml"):
        path = "recipe/meta.yaml"
    elif os.path.exists("recipe/recipe.yaml"):
        path = "recipe/recipe.yaml"
    else:
        return None

    with open(path) as fp:
        return fp.read()


def _get_recipe_dummy_meta(recipe_content):
    keep_lines = []
    skip = 0
    for line in recipe_content.splitlines():
        if line.strip().startswith("extra:"):
            skip += 1
        if skip > 0:
            keep_lines.append(_filter_jinja2(line))
    assert skip == 1, "team update failed due to > 1 'extra:' sections"
    return DummyMeta("\n".join(keep_lines))


class Username2IDMapping(Migrator):
    main_branch_only = True
    max_processes = 1

    def migrate(self, feedstock, branch):
        if os.path.exists(UNAME2ID_FILE):
            print("    username to id mapping already exists!", flush=True)
            # migration done, make a commit, lots of API calls
            return True, False, False

        gh = _gh()
        org = gh.get_organization("conda-forge")

        # for this migration to the new ID recording system, we use
        # the github team, not the recipe. The reason is that the github
        # team's list of usernames is built by unique IDs. So it has tracked
        # and properly retained permissions for people who have changed their
        # username. We want to write the IDs of the people on the feedstock
        # as it should be if we had done the same.
        fs_team = org.get_team_by_slug(feedstock)
        maintainers = {e.login.lower() for e in fs_team.get_members()}

        uname2id_mapping = {}
        for uname in maintainers:
            try:
                uid = gh.get_user(uname).id
            except Exception:
                uid = None

            uname2id_mapping[uname] = uid

        if any(val is None for val in uname2id_mapping.values()):
            # migration done, make a commit, lots of API calls
            return False, False, True

        print("    got username to id mapping", flush=True)

        with open(UNAME2ID_FILE, "w") as fp:
            fp.write(json.dumps(uname2id_mapping, sort_keys=True, indent=2))

        subprocess.run(
            ["git", "add", "-f", UNAME2ID_FILE],
            check=True,
        )

        print("    wrote username to id mapping file", flush=True)

        # now we remove any user in a recipe who does not exist
        print("    looking for maintainers to remove from the recipe", flush=True)

        # DO NOT USE THIS CODE TO SET IDs
        recipe_content = _get_recipe_contents()
        meta = _get_recipe_dummy_meta(recipe_content)
        recipe_maintainers = set(
            meta.meta.get("extra", {}).get("recipe-maintainers", []) or []
        )
        recipe_maintainers = {m.lower() for m in recipe_maintainers}
        recipe_maintainers = {m for m in recipe_maintainers if "/" not in m}
        maint_to_remove = set()
        for maint in recipe_maintainers:
            try:
                gh.get_user(maint)
            except Exception:
                if maint not in uname2id_mapping:
                    maint_to_remove.add(maint)

        if maint_to_remove:
            print("    found maintainers to remove from the recipe", flush=True)
            new_lines = []
            for line in recipe_content.splitlines():
                remove_line = False
                for maint in maint_to_remove:
                    if line.lstrip().startswith(f"- {maint}"):
                        remove_line = True

                if not remove_line:
                    new_lines.append(line)

            wrote = False
            for pth in ["recipe/meta.yaml", "recipe/recipe.yaml"]:
                if os.path.exists(pth):
                    with open(pth, "w") as fp:
                        fp.write("\n".join(new_lines))

                    subprocess.run(
                        ["git", "add", "-f", pth],
                        check=True,
                    )
                    wrote = True
                    break

            assert wrote, "Could not write new recipe!"
            print("    removed maintainers from the recipe", flush=True)

        # migration done, make a commit, lots of API calls
        return True, True, True
