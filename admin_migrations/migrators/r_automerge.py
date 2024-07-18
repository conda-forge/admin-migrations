import os
import subprocess

from ruamel.yaml import YAML

from .base import Migrator


def _has_r_team():
    yaml = YAML()

    if os.path.exists(os.path.join("recipe", "meta.yaml")):
        meta_loc = os.path.join("recipe", "meta.yaml")
    elif os.path.exists(os.path.join("recipe", "recipe", "meta.yaml")):
        meta_loc = os.path.join("recipe", "recipe", "meta.yaml")

    with open(meta_loc, "r") as fp:
        keep_lines = []
        skip = True
        for line in fp.readlines():
            if line.startswith("extra:"):
                skip = False
            if not skip:
                keep_lines.append(line)

    maints = yaml.load("".join(keep_lines))["extra"]["recipe-maintainers"]
    maints = [m.strip() for m in maints]
    return "conda-forge/r" in maints

def _has_r_team_rattler_build():
    """Check if the recipe has a conda-forge/r maintainer. Works with rattler-build recipes"""
    yaml = YAML()
    recipe_location = os.path.join("recipe", "recipe.yaml")
    if not os.path.exists(recipe_location):
        return False
    try:
        with open("recipe/recipe.yaml", "r") as file:
            yaml = yaml.load(file)
        if "extra" in yaml:
            if "recipe-maintainers" in yaml["extra"]:
                maints = yaml["extra"]["recipe-maintainers"]
                maints = [m.strip() for m in maints]
                return "conda-forge/r" in maints
    except Exception as e:
        return False


def _has_cran_url():
    stop_tokens = ["build:", "requirements:", "test:", "about:", "extra:"]

    if os.path.exists(os.path.join("recipe", "meta.yaml")):
        meta_loc = os.path.join("recipe", "meta.yaml")
    elif os.path.exists(os.path.join("recipe", "recipe", "meta.yaml")):
        meta_loc = os.path.join("recipe", "recipe", "meta.yaml")

    with open(meta_loc, "r") as fp:
        in_source_section = False
        for line in fp.readlines():
            if line.startswith("source:"):
                in_source_section = True
            elif any(line.startswith(t) for t in stop_tokens):
                break

            if (
                in_source_section and
                (
                    # this same set of slugs is used by the autotick bot
                    # https://github.com/regro/cf-scripts/blob/master/conda_forge_tick/migrators/version.py#L71
                    "cran_mirror" in line
                    or "cran.r-project.org/src/contrib" in line
                )
            ):
                return True

    return False

def _has_cran_url_rattler_build():
    """Check if the recipe has a cran url in the source section. Works with rattler-build recipes
    Collect all urls in the source section and check if any of them are cran urls.
    Can be conditionally a single source or a list of sources
    i.e.
    ```
     source: # case 1
       url: https://cran.r-project.org/src/contrib/foo
    ```
     or
    ```
     source: # case 2
       - url: https://cran.r-project.org/src/contrib/foo
       - url: https://cran.r-project.org/src/contrib/bar
    ```
    we can also contain an conditional, these may not be nested:
    ```
     if something:
     then:
         - url: https://cran.r-project.org/src/contrib/foo
     else:
         - url: https://cran.r-project.org/src/contrib/bar
    ```
    Which can in turn contain a source or a list of sources (case 1 or case 2)
    """

    yaml = YAML()
    recipe_location = os.path.join("recipe", "recipe.yaml")
    MIRROR = "cran_mirror"
    CONTRIB = "cran.r-project.org/src/contrib"


    # Helper functions
    def _check_source(source):
        """Check if a source has a cran url"""
        if source and "url" in source:
            return MIRROR in source["url"] or CONTRIB in source["url"]
        return False

    def _check_list_of_sources(sources):
        """Check if a list of sources has a cran url"""
        for source in sources:
            if _check_source(source):
                return True
        return False

    def _check_source_or_list_of_sources(branch):
        """Check if a branch of a conditional has a cran url
        which can again be a source or a list of sources
        """
        if branch:
            if isinstance(branch, dict) and "url" in branch:
                return _check_source(branch)
            if isinstance(branch, list):
                return _check_list_of_sources(branch)

    def _check_conditional(then, elze):
        """Check if a conditional has a cran url"""
        if then:
            # Check the then branch of the conditional
            return _check_source_or_list_of_sources(then)
        if elze:
            # Check the else branch of the conditional
            return _check_source_or_list_of_sources(elze)
        return False

    def _check_source_or_conditional(source):
        """Check if a source has a cran url or if it is a conditional that may contain a cran url"""
        if _check_source(source):
            return True
        return _check_conditional(source.get("then"), source.get("else"))

    if not os.path.exists(recipe_location):
        return False
    try:
        with open("recipe/recipe.yaml", "r") as file:
            recipe = yaml.load(file)
            # Check for top-level source attribute(s)
            if "source" in recipe:
                sources = yaml["source"]
                if isinstance(sources, dict):
                    # Can only be a source or a conditional
                    return _check_source_or_conditional(sources)
                elif isinstance(sources, list):
                    for source in sources:
                        # A list that can contain both direct sources and conditionals
                        if _check_source_or_conditional(source):
                            return True
            # There can also be outputs that produce sources and no top level sources
            # but I think this is also ignored in the `meta.yaml` case, so ignoring it here as well
    except Exception as e:
        return False

    return False


class RAutomerge(Migrator):
    """Adds bot automerge to any feedstock that has

        1. r-* in the name
        2. has conda-forge/r on the maintainers list
        3. uses the {{ cran_mirror }} jinja2 variable or has a cran url
    """
    def migrate(self, feedstock, branch):
        print("    r team:", _has_r_team(), flush=True)
        print("    cran url:", _has_cran_url(), flush=True)

        if (
            feedstock.startswith("r-")
            and feedstock != "r-base"
            and (_has_r_team() or _has_r_team_rattler_build())
            and (_has_cran_url() or _has_cran_url_rattler_build())
        ):
            with open("conda-forge.yml", "r") as fp:
                meta_yaml = fp.read()

            if meta_yaml.strip() == "[]" or meta_yaml.strip() == "[ ]":
                cfg = {}
            else:
                yaml = YAML()
                cfg = yaml.load(meta_yaml)

            # already done or maybe to False locally
            if "bot" in cfg and "automerge" in cfg["bot"]:
                print(
                    "    bot.automerge already set:", cfg["bot"]["automerge"],
                    flush=True,
                )
                return True, False, False

            cfg["bot"] = {"automerge": True}

            with open("conda-forge.yml", "w") as fp:
                yaml.dump(cfg, fp)

            subprocess.run(
                ["git", "add", "conda-forge.yml"],
                check=True,
            )

            # did migration, make a commit, no api calls
            return True, True, False
        else:
            # no migration, no commit needs to be made, no api calls
            return False, False, False
