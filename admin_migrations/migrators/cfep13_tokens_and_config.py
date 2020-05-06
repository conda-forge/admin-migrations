import os
import subprocess
import requests

from ruamel.yaml import YAML

from .base import Migrator


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

        # register a feedstock token
        r = requests.post(
            "https://conda-forge.herokuapp.com/feedstock-tokens/register",
            json={"feedstock": feedstock},
            headers={"FEEDSTOCK_TOKEN": os.environ["STAGED_RECIPES_FEEDSTOCK_TOKEN"]}
        )
        r.raise_for_status()

        # register the staging binstar token
        subprocess.run(
            "conda smithy update-binstar-token "
            "--without-appveyor --token_name STAGING_BINSTAR_TOKEN",
            shell=True,
            check=True
        )

        # set the param and write
        cfg["conda_forge_output_validation"] = True
        with open("conda-forge.yml", "w") as fp:
            yaml.dump(cfg, fp)
        subprocess.run(
            ["git", "add", "conda-forge.yml"],
            check=True,
        )

        # migration done, make a commit, lots of API calls
        return True, True, True
