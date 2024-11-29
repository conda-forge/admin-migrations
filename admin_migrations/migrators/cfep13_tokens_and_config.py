import glob
import json
import os
import subprocess

import conda_build
from conda_smithy.feedstock_tokens import feedstock_token_exists
from rattler_build_conda_compat.render import render_recipe as render_rattler_build
from ruamel.yaml import YAML

from .base import Migrator

TOKENS_REPO = "https://${GITHUB_TOKEN}@github.com/conda-forge/feedstock-tokens.git"
OUTPUTS_REPO = "https://${GITHUB_TOKEN}@github.com/conda-forge/feedstock-outputs.git"


def _read_conda_forge_yaml(yaml):
    if os.path.exists("conda-forge.yml"):
        with open("conda-forge.yml") as fp:
            meta_yaml = fp.read()

        if (
            meta_yaml is None
            or meta_yaml.strip() == "[]"
            or meta_yaml.strip() == "[ ]"
            or len(meta_yaml) == 0
            or len(meta_yaml.strip()) == 0
        ):
            cfg = {}
        else:
            cfg = yaml.load(meta_yaml)
    else:
        meta_yaml = ""
        cfg = {}

    return cfg


class CFEP13TurnOff(Migrator):
    max_migrate = 200

    def migrate(self, feedstock, branch):
        yaml = YAML()
        cfg = _read_conda_forge_yaml(yaml)

        if cfg.get("conda_forge_output_validation"):
            # set the param and write
            cfg["conda_forge_output_validation"] = False
            with open("conda-forge.yml", "w") as fp:
                yaml.dump(cfg, fp)
            subprocess.run(
                ["git", "add", "conda-forge.yml"],
                check=True,
            )
            print("    updated conda-forge.yml", flush=True)

            # migration done, make a commit, lots of API calls
            return True, True, False
        else:
            # migration done, no commits, no API calls
            return True, False, False


def _register_feedstock_token(feedstock):
    """Generate and register feedstock tokens."""

    if feedstock_token_exists("conda-forge", feedstock + "-feedstock", TOKENS_REPO):
        print("    feedstock token already exists", flush=True)
        return

    try:
        subprocess.run(
            ["conda-smithy", "generate-feedstock-token"],
            check=True,
        )

        subprocess.run(
            ["conda-smithy", "register-feedstock-token"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print("    feedstock token registration failed", flush=True)
        raise e
    finally:
        # remove both paths due to change in smithy
        try:
            if feedstock.endswith("-feedstock"):
                feedstock_name = feedstock[: -len("-feedstock")]
            else:
                feedstock_name = feedstock
            token_path = os.path.expanduser(
                "~/.conda-smithy/conda-forge_%s_feedstock.token" % feedstock_name
            )
            os.remove(token_path)
        except Exception:
            pass

        try:
            token_path = os.path.expanduser(
                "~/.conda-smithy/conda-forge_%s.token" % feedstock
            )
            os.remove(token_path)
        except Exception:
            pass


def _get_sharded_path(output):
    chars = [c for c in output if c.isalnum()]
    while len(chars) < 3:
        chars.append("z")
    return os.path.join("outputs", chars[0], chars[1], chars[2], output + ".json")


def _register_feedstock_outputs(feedstock):
    unames = set()

    is_rattler_build = False
    # this is a common way in which feedstocks are wrong
    if os.path.exists("recipe/meta.yaml"):
        recipe_loc = "recipe"
    elif os.path.exists("recipe/recipe/meta.yaml"):
        recipe_loc = "recipe/recipe"
    elif os.path.exists("recipe/recipe.yaml"):
        recipe_loc = "recipe/recipe.yaml"
        is_rattler_build = True
    else:
        raise RuntimeError("could not find recipe location!")

    cbcs = sorted(glob.glob(os.path.join(".ci_support", "*.yaml")))
    for cbc_fname in cbcs:
        # we need to extract the platform (e.g., osx, linux) and arch (e.g., 64, aarm64)
        # conda smithy forms a string that is
        #
        #  {{ platform }} if arch == 64
        #  {{ platform }}_{{ arch }} if arch != 64
        #
        # Thus we undo that munging here.
        _parts = os.path.basename(cbc_fname).split("_")
        platform = _parts[0]
        arch = _parts[1]
        if arch not in ["32", "aarch64", "ppc64le", "armv7l"]:
            arch = "64"

        # parse the channel sources from the CBC
        parser = YAML(typ="jinja2")
        parser.indent(mapping=2, sequence=4, offset=2)
        parser.width = 320

        with open(cbc_fname) as fp:
            cbc_cfg = parser.load(fp.read())

        if "channel_sources" in cbc_cfg:
            channel_sources = cbc_cfg["channel_sources"][0].split(",")
        else:
            channel_sources = ["conda-forge"]

        if "msys2" not in channel_sources:
            channel_sources.append("msys2")

        # here we extract the conda build config in roughly the same way that
        # it would be used in a real build
        config = conda_build.config.get_or_merge_config(
            None,
            exclusive_config_file=cbc_fname,
            platform=platform,
            arch=arch,
        )
        cbc, _ = conda_build.variants.get_package_combined_spec(
            recipe_loc, config=config
        )

        if not is_rattler_build:
            # now we render the meta.yaml into an actual recipe
            metas = conda_build.api.render(
                recipe_loc,
                platform=platform,
                arch=arch,
                ignore_system_variants=True,
                variants=cbc,
                permit_undefined_jinja=True,
                finalize=False,
                bypass_env_check=True,
                channel_urls=channel_sources,
            )
            for m, _, _ in metas:
                unames.add(m.name())
        else:
            # Render rattler-build recipe.yaml
            metas = render_rattler_build(recipe_loc, config, cbc)
            for meta in metas:
                unames.add(meta.get_section("package").get("name"))

    print("    output names:", unames, flush=True)

    for name in unames:
        sharded_name = _get_sharded_path(name)
        outpth = os.path.join(
            os.environ["FEEDSTOCK_OUTPUTS_REPO"],
            sharded_name,
        )

        subprocess.run(
            ["git", "pull", "--quiet"],
            check=True,
            cwd=os.environ["FEEDSTOCK_OUTPUTS_REPO"],
        )

        if not os.path.exists(outpth):
            os.makedirs(os.path.dirname(outpth), exist_ok=True)
            with open(outpth, "w") as fp:
                json.dump({"feedstocks": [feedstock]}, fp)

            subprocess.run(
                ["git", "add", sharded_name],
                check=True,
                cwd=os.environ["FEEDSTOCK_OUTPUTS_REPO"],
            )

            subprocess.run(
                [
                    "git",
                    "commit",
                    "-am",
                    "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** "
                    "added output %s for conda-forge/%s" % (name, feedstock),
                ],
                check=True,
                cwd=os.environ["FEEDSTOCK_OUTPUTS_REPO"],
            )

            subprocess.run(
                ["git", "push", "--quiet"],
                check=True,
                cwd=os.environ["FEEDSTOCK_OUTPUTS_REPO"],
            )
            print("    added output:", name, flush=True)


class CFEP13TokensAndConfig(Migrator):
    max_workers = 1
    max_migrate = 200

    def migrate(self, feedstock, branch):
        yaml = YAML()
        cfg = _read_conda_forge_yaml(yaml)

        if (
            "conda_forge_output_validation" in cfg
            and cfg["conda_forge_output_validation"]
            and feedstock_token_exists(
                "conda-forge", feedstock + "-feedstock", TOKENS_REPO
            )
        ):
            # migration done, no commits, no API calls
            return True, False, False

        if branch == "master" or branch == "main":
            # register a feedstock token
            # this call is idempotent if the token already exists
            _register_feedstock_token(feedstock)
            print("    registered feedstock token", flush=True)

            # register the staging binstar token
            subprocess.run(
                "conda smithy update-binstar-token "
                "--without-appveyor --token_name STAGING_BINSTAR_TOKEN",
                shell=True,
                check=True,
            )
            print("    added staging binstar token", flush=True)

            # register the outputs
            _register_feedstock_outputs(feedstock)
            print("    added output to outputs repo", flush=True)

        # set the param and write
        cfg["conda_forge_output_validation"] = True
        with open("conda-forge.yml", "w") as fp:
            yaml.dump(cfg, fp)
        subprocess.run(
            ["git", "add", "conda-forge.yml"],
            check=True,
        )
        print("    updated conda-forge.yml", flush=True)

        # migration done, make a commit, lots of API calls
        return True, True, True
