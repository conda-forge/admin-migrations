import os
import json


class Migrator(object):
    def __init__(self):
        self._load_done_table()

    def _load_done_table(self):
        fname = "data/%s.json" % self.__class__.__name__
        if not os.path.exists(fname):
            blob = {"done": []}
        else:
            with open(fname, "r") as fp:
                blob = json.load(fp)
        self._done_table = blob

        print("migrator %s: done %d" % (
            self.__class__.__name__,
            len(blob["done"]),
        ))

    def skip(self, feedstock):
        if feedstock in self._done_table["done"]:
            return True
        else:
            return False

    def migrate(self):
        """Migrate the feedstock.

        This function is invoked with the feedstock as the current
        working directory.

        Implementations should make any desired changes and then "git add"
        the resulting files.

        Finally, always two boolean values.

        The first should be True if the migration worked, False otherwise.
        The second should be True if a commit should be made, False otherwise.
        """
        raise NotImplementedError()

    def message(self):
        return "admin migration %s" % self.__class__.__name__

    def record(self, feedstock):
        fname = "data/%s.json" % self.__class__.__name__
        if not os.path.exists(fname):
            blob = {"done": []}
        else:
            with open(fname, "r") as fp:
                blob = json.load(fp)

        blob["done"].append(feedstock)

        with open(fname, "w") as fp:
            json.dump(blob, fp)
