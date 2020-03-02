import os
import json
import time

import requests
import tempfile
import contextlib

from admin_migrations.migrators import AutomergeAndRerender

MAX_MIGRATE = 200
MAX_SECONDS = 45 * 60

# https://stackoverflow.com/questions/6194499/pushd-through-os-system
@contextlib.contextmanager
def pushd(new_dir):
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(previous_dir)


def _load_feedstock_data():
    r = requests.get(
        "https://raw.githubusercontent.com/regro/"
        "cf-graph-countyfair/master/names.txt"
    )
    if r.status_code != 200:
        raise RuntimeError("could not get feedstocks!")

    feedstocks = [f for f in r.text.split("\n") if len(f) > 0]

    if not os.path.exists("data/feedstocks.json"):
        blob = {
            'current': 0,
            "feedstocks": {
                f: 0 for f in sorted(feedstocks)
            }
        }
    else:
        with open("data/feedstocks.json", "r") as fp:
            blob = json.load(fp)

    new_feedstocks = set(feedstocks) - set([k for k in blob["feedstocks"]])
    if len(new_feedstocks) > 0:
        for f in new_feedstocks:
            blob["feedstocks"][f] = blob["current"]

    return blob


def _commit_data():
    print("\nsaving data...")
    os.system("git add data/*.json")
    os.system("git commit -m 'data for admin migration run'")
    os.system(
        "git remote set-url --push origin https://%s"
        "@github.com/conda-forge/admin-migrations.git" % os.environ["GITHUB_TOKEN"])
    os.system("git push")


def run_migrators(feedstock, migrators):
    migrators_to_record = []

    with tempfile.TemporaryDirectory() as tmpdir:
        with pushd(tmpdir):
            os.system(
                "git clone https://%s@github.com/"
                "conda-forge/%s-feedstock.git" % (
                    os.environ["GITHUB_TOKEN"],
                    feedstock,
                )
            )

            with pushd("%s-feedstock" % feedstock):
                os.system(
                    "git remote set-url --push origin https://%s"
                    "@github.com/conda-forge/%s-feedstock.git" % (
                        os.environ["GITHUB_TOKEN"],
                        feedstock,
                    )
                )

                for m in migrators:
                    print("\nmigrator %s" % m.__class__.__name__)
                    if m.skip(feedstock):
                        continue
                    try:
                        worked, commit_me = m.migrate()
                    except Exception:
                        worked = False
                        commit_me = False

                    if commit_me:
                        os.system(
                            "git commit -m '[ci skip] [skip ci] [cf admin skip] "
                            "***NO_CI*** %s'" % m.message()
                        )
                        os.system("git push")
                    if worked:
                        migrators_to_record.append(m)

                    print(" ")

    for m in migrators_to_record:
        m.record(feedstock)


def main():
    migrators = [AutomergeAndRerender()]

    feedstocks = _load_feedstock_data()
    current_num = feedstocks["current"]
    next_num = (current_num + 1) % 2

    num_done_prev = sum(v == next_num for v in feedstocks["feedstocks"].values())

    num_done = 0
    start_time = time.time()
    for f in feedstocks["feedstocks"]:
        # out of time?
        if time.time() - start_time > MAX_SECONDS:
            break

        # did too many?
        if num_done >= MAX_MIGRATE:
            break

        # did we do this one?
        if feedstocks["feedstocks"][f] != current_num:
            continue

        # migrate
        _start = time.time()

        print("=" * 80)
        print("=" * 80)
        print("=" * 80)
        print("migrating %s" % f)

        run_migrators(f, migrators)
        feedstocks["feedstocks"][f] = next_num
        num_done += 1

        print("took %s seconds" % (time.time() - _start))
        print("done %d out of %d for this round" % (
            num_done_prev + num_done,
            len(feedstocks["feedstocks"]),
        ))
        print("can migrate ~%d more feedstocks" % (
            int(num_done / (time.time() - start_time) * MAX_SECONDS)
        ))

        print(" ")

        # sleep a bit
        time.sleep(10)

    if all(v == next_num for v in feedstocks["feedstocks"].values()):
        print("completed all feedstocks - starting over!")
        feedstocks["current"] = next_num

    with open("data/feedstocks.json", "w") as fp:
        json.dump(feedstocks, fp)

    _commit_data()
