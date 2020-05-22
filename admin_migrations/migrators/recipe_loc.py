import os
import subprocess

from .base import Migrator


class RecipeLocation(Migrator):
    def migrate(self, feedstock, branch):
        if (
            os.path.exists("recipe/recipe/meta.yaml")
            and not os.path.exists("recipe/meta.yaml")
        ):
            subprocess.run(
                ["git", "mv", "recipe/recipe/*", "recipe/."],
                check=True,

            )
            subprocess.run(
                ["git", "add", "recipe/*"],
                check=True,
            )

            # repo is migrated, commit, no api calls
            return True, True, False
        else:
            # repo is migrated, no commits, no api calls
            return True, False, False
