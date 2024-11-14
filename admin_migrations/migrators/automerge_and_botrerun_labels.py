import functools
import os

import github

from .base import Migrator

BOT_RERUN = (
    "bot-rerun",
    "191970",
    "Instruct the bot to retry the PR",
)

AUTOMERGE = (
    "automerge",
    "0e8a16",
    "Merge the PR when CI passes",
)


@functools.lru_cache(maxsize=1)
def _gh():
    return github.Github(os.environ["GITHUB_TOKEN"])


class AutomergeAndBotRerunLabels(Migrator):
    main_branch_only = True

    def migrate(self, feedstock, branch):
        try:
            repo = _gh().get_repo("conda-forge/%s-feedstock" % feedstock)
            if repo.archived:
                return True, False, True

            labels = [lb for lb in repo.get_labels()]

            for label_data in [BOT_RERUN, AUTOMERGE]:
                target_label = None
                for lb in labels:
                    if lb.name == label_data[0]:
                        target_label = lb
                        break

                if target_label:
                    if (
                        target_label.color != label_data[1]
                        or target_label.description != label_data[2]
                    ):
                        target_label.edit(label_data[0], label_data[1], label_data[2])
                        print("    edited:", label_data[0], flush=True)
                else:
                    repo.create_label(label_data[0], label_data[1], label_data[2])
                    print("    created:", label_data[0], flush=True)

            # worked, commit me, made API calls
            return True, False, True
        except (github.GithubException, github.BadAttributeException) as e:
            print("ERROR: %s" % repr(e), flush=True)
            return False, False, True
