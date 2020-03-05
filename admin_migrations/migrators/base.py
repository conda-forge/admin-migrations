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
        """Return true if the migration should be skipped for this feedstock.

        Note this method cannot depend on the feedstock contents.
        """
        if feedstock in self._done_table["done"]:
            return True
        else:
            return False

    def migrate(self, feedstock):
        """Migrate the feedstock.

        This function is invoked with the feedstock as the current
        working directory.

        Implementations should make any desired changes and then "git add"
        the resulting files.

        Finally, always return three boolean values.

        The first should be True if the migration worked, False otherwise.
        The second should be True if a commit should be made, False otherwise.
        The third should be True if the migrator made any github API calls,
        False otherwise.

        By returning True for the migration working, you can mark already migrated
        feedstocks as migrated in the migrator metadata. So for example, if you
        are adding a file `.github/blah` to feedstocks, you can test for this file
        and if it is there, then return `True, False`. This marks the migration
        as done but tells the code not to make any commits (since the file is already)
        there.

        Parameters
        ----------
        feedstock : str
            The name of the feedstock without "-feedstock" (e.g., "python"
            and not "python-feedstock").
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
