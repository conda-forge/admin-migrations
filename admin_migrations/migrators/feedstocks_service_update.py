import os
import shutil
import tempfile
import time

import git
import github

from .base import Migrator


class FeedstocksServiceUpdate(Migrator):
    main_branch_only = True
    max_processes = 1

    def migrate(self, feedstock, branch):
        org_name = "conda-forge"

        # code here os from webservices repo
        repo_name = feedstock + "-feedstock"
        name = repo_name[: -len("-feedstock")]

        tmp_dir = None
        try:
            tmp_dir = tempfile.mkdtemp("_recipe")

            feedstocks_url = (
                "https://x-access-token:{}@github.com/conda-forge/feedstocks.git"
                "".format(os.environ["GITHUB_TOKEN"])
            )
            feedstocks_repo = git.Repo.clone_from(
                feedstocks_url,
                tmp_dir,
                depth=1,
            )
            print("    cloned feedstocks repo", flush=True)

            # Get the submodule
            # sometimes the webhook outpaces other bits of the API so we try a bit
            for i in range(5):
                try:
                    gh = github.Github(os.environ["GITHUB_TOKEN"])
                    default_branch = gh.get_repo(
                        f"{org_name}/{repo_name}"
                    ).default_branch
                    break
                except Exception as e:
                    if i < 4:
                        time.sleep(0.050 * 2**i)
                        continue
                    else:
                        raise e

            feedstock_submodule = feedstocks_repo.create_submodule(
                name=name,
                path=os.path.join("feedstocks", name),
                url=f"https://github.com/{org_name}/{repo_name}.git",
                branch=default_branch,
            )

            # Update the feedstocks submodule
            with feedstock_submodule.config_writer() as cfg:
                cfg.config.set_value(
                    'submodule "%s"' % name,
                    "branch",
                    "refs/heads/%s" % default_branch,
                )
            feedstock_submodule.update(
                init=True, recursive=False, force=True, to_latest_revision=True
            )
            feedstocks_repo.git.add([".gitmodules", feedstock_submodule.path])
            print("    updated submodule", flush=True)

            # Submit changes
            if feedstocks_repo.is_dirty(working_tree=False, untracked_files=True):
                feedstocks_repo.index.commit(
                    f"Updated the {name} feedstock.",
                )
                feedstocks_repo.remote().pull(rebase=True)
                feedstocks_repo.remote().push()
            print("    pushed if needed", flush=True)

        finally:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir)

        # migration done, make a commit, lots of API calls
        return True, False, True
