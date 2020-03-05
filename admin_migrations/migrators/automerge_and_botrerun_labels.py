import os
import github

from .base import Migrator

GH = github.Github(os.environ['GITHUB_TOKEN'])

BOT_RERUN = (
    "bot-rerun",
    "191970",
    "Merge the PR when CI passes",
)

AUTOMERGE = (
    "automerge",
    "0e8a16",
    "Apply this label if you want the bot to retry issuing a particular pull-request",
)


class AutomergeAndBotRerunLabels(Migrator):
    def migrate(self, feedstock):
        try:
            repo = GH.get_repo("conda-forge/%s-feedstock" % feedstock)
            labels = [l for l in repo.get_labels()]

            for label_data in [BOT_RERUN, AUTOMERGE]:
                target_label = None
                for l in labels:
                    if l.name == label_data[0]:
                        target_label = l
                        break

                if (
                    target_label and
                    (
                        target_label.color != label_data[1] or
                        target_label.description != label_data[2]
                    )
                ):
                    target_label.edit(label_data[0], label_data[1], label_data[2])
                else:
                    repo.create_label(label_data[0], label_data[1], label_data[2])

            # worked, commit me, made API calls
            return True, False, True
        except (github.GithubException, github.BadAttributeException) as e:
            print("ERROR: %s" % repr(e))
            return False, False, True
