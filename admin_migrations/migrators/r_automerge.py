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


class RAutomerge(Migrator):
    """Adds bot automerge to any feedstock that has

        1. r-* in the name
        2. has conda-forge/r on the maintainers list
        3. uses the {{ cran_mirror }} jinja2 variable or has a cran url
    """
    def migrate(self, feedstock, branch):
        print("    r team:", _has_r_team())
        print("    cran url:", _has_cran_url())

        if (
            feedstock.startswith("r-")
            and feedstock != "r-base"
            and _has_r_team()
            and _has_cran_url()
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
                print("    bot.automerge already set:", cfg["bot"]["automerge"])
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
