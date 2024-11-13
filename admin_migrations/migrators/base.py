import json
import os


class Migrator:
    # set this to true if the admin migration runs for the main branch only
    # this can be used for migrations that update CI services used by all branches
    main_branch_only = False
    max_processes = 100000

    def __init__(self):
        self._load_done_table()

    def _load_done_table(self):
        fname = "data/%s.json" % self.__class__.__name__
        if not os.path.exists(fname):
            blob = {}
        else:
            with open(fname) as fp:
                blob = json.load(fp)
        self._done_table = blob

        print(
            "migrator %s: done %d"
            % (
                self.__class__.__name__,
                len(blob),
            ),
            flush=True,
        )

    def skip(self, feedstock, branch):
        """Return true if the migration should be skipped for this feedstock
        and branch.

        Note this method cannot depend on the feedstock contents.
        """
        if branch != "main":
            return self._done_table.get(feedstock, {}).get(branch, False)
        else:
            return self._done_table.get(feedstock, {}).get(
                "master", False
            ) or self._done_table.get(feedstock, {}).get("main", False)

    def migrate(self, feedstock, branch):
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
        branch : str
            Which branch of the feedstock the migrator is being called on.
        """
        raise NotImplementedError()

    def message(self):
        return "admin migration %s" % self.__class__.__name__

    def record(self, feedstock, branch):
        fname = "data/%s.json" % self.__class__.__name__
        if not os.path.exists(fname):
            blob = {}
        else:
            with open(fname) as fp:
                blob = json.load(fp)

        if feedstock not in blob:
            blob[feedstock] = {}
        blob[feedstock][branch] = True

        with open(fname, "w") as fp:
            json.dump(blob, fp, indent=2, sort_keys=True)
