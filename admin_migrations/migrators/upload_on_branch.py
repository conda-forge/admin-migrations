import subprocess

from ruamel.yaml import YAML

from .base import Migrator


class UploadOnBranch(Migrator):
    """Enable upload_on_branch for feedstocks."""

    continual = True

    def migrate(self, feedstock, branch):
        with open("conda-forge.yml") as fp:
            meta_yaml = fp.read()

        if meta_yaml.strip() == "[]" or meta_yaml.strip() == "[ ]":
            cfg = {}
        else:
            yaml = YAML()
            cfg = yaml.load(meta_yaml)

        commit = False

        if not cfg.get("upload_on_branch", None) and branch != "main":
            cfg["upload_on_branch"] = branch

            with open("conda-forge.yml", "w") as fp:
                yaml.dump(cfg, fp)

            subprocess.run(
                ["git", "add", "conda-forge.yml"],
                check=True,
            )

            commit = True

        # did migration, make a commit, no api calls
        # return True, True, False
        # this migrator is never done
        return False, commit, False
