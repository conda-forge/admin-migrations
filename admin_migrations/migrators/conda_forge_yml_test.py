import subprocess

from ruamel.yaml import YAML

from .base import Migrator


class CondaForgeYAMLTest(Migrator):
    """Cleanup conda-forge.yml test_on_native_only"""

    def migrate(self, feedstock, branch):
        with open("conda-forge.yml") as fp:
            meta_yaml = fp.read()

        if meta_yaml.strip() == "[]" or meta_yaml.strip() == "[ ]":
            cfg = {}
        else:
            yaml = YAML()
            cfg = yaml.load(meta_yaml)

        if "test_on_native_only" not in cfg:
            # no migration, no commit needs to be made, no api calls
            return False, False, False

        value = cfg["test_on_native_only"]
        del cfg["test_on_native_only"]
        if str(value) in ["True", "true"] and "test" not in cfg:
            cfg["test"] = "native_and_emulated"

        with open("conda-forge.yml", "w") as fp:
            yaml.dump(cfg, fp)

        subprocess.run(
            ["git", "add", "conda-forge.yml"],
            check=True,
        )

        # did migration, make a commit, no api calls
        # return True, True, False
        # this migrator is never done
        return False, False, False
