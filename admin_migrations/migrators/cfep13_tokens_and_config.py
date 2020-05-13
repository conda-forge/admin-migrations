import os
import subprocess

from ruamel.yaml import YAML

from conda_smithy.feedstock_tokens import feedstock_token_exists

from .base import Migrator

TOKENS_REPO = "https://${GH_TOKEN}@github.com/conda-forge/feedstock-tokens.git"


class CFEP13TurnOff(Migrator):
    def migrate(self, feedstock, branch):

        with open("conda-forge.yml", "r") as fp:
            meta_yaml = fp.read()

        if meta_yaml.strip() == "[]" or meta_yaml.strip() == "[ ]":
            cfg = {}
        else:
            yaml = YAML()
            cfg = yaml.load(meta_yaml)

        if (
            "conda_forge_output_validation" in cfg
            and cfg["conda_forge_output_validation"]
        ):
            # set the param and write
            cfg["conda_forge_output_validation"] = False
            with open("conda-forge.yml", "w") as fp:
                yaml.dump(cfg, fp)
            subprocess.run(
                ["git", "add", "conda-forge.yml"],
                check=True,
            )
            print("    updated conda-forge.yml")

            # migration done, make a commit, lots of API calls
            return True, True, False
        else:
            # migration done, no commits, no API calls
            return True, False, False


def _register_feedstock_token(feedstock):
    """Generate and register feedstock tokens."""

    if feedstock_token_exists("conda-forge", feedstock, TOKENS_REPO):
        print("    feedstock token already exists")
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
        print("    feedstock token registration failed")
        raise e
    finally:
        # remove both paths due to change in smithy
        try:
            if feedstock.endswith("-feedstock"):
                feedstock_name = feedstock[:-len("-feedstock")]
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
                "~/.conda-smithy/conda-forge_%s.token" % feedstock)
            os.remove(token_path)
        except Exception:
            pass


class CFEP13TokensAndConfig(Migrator):
    def migrate(self, feedstock, branch):

        with open("conda-forge.yml", "r") as fp:
            meta_yaml = fp.read()

        if meta_yaml.strip() == "[]" or meta_yaml.strip() == "[ ]":
            cfg = {}
        else:
            yaml = YAML()
            cfg = yaml.load(meta_yaml)

        if (
            "conda_forge_output_validation" in cfg
            and cfg["conda_forge_output_validation"]
        ):
            # migration done, no commits, no API calls
            return True, False, False

        if branch == "master":
            # register a feedstock token
            _register_feedstock_token(feedstock)
            print("    registered feedstock token")

            # register the staging binstar token
            subprocess.run(
                "conda smithy update-binstar-token "
                "--without-appveyor --token_name STAGING_BINSTAR_TOKEN",
                shell=True,
                check=True
            )
            print("    added staging binstar token")

        # set the param and write
        cfg["conda_forge_output_validation"] = True
        with open("conda-forge.yml", "w") as fp:
            yaml.dump(cfg, fp)
        subprocess.run(
            ["git", "add", "conda-forge.yml"],
            check=True,
        )
        print("    updated conda-forge.yml")

        # migration done, make a commit, lots of API calls
        return True, True, True
