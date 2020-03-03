import os
import json
import time
import tempfile
import contextlib
import subprocess
import requests

from admin_migrations.migrators import AutomergeAndRerender

MAX_MIGRATE = 1000
MAX_SECONDS = 50 * 60


def _repo_is_archived(feedstock):
    headers = {
        "authorization": "Bearer %s" % os.environ['GITHUB_TOKEN'],
        'content-type': 'application/json',
    }
    r = requests.get(
        "https://api.github.com/repos/conda-forge/%s-feedstock" % feedstock,
        headers=headers,
    )
    return r.json()["archived"]


# https://stackoverflow.com/questions/6194499/pushd-through-os-system
@contextlib.contextmanager
def pushd(new_dir):
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(previous_dir)


def _run_git_command(args):
    subprocess.run(['git'] + args, check=True)


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
            blob["feedstocks"][f] = (blob["current"] + 1) % 2

    return blob


def _commit_data():
    print("\nsaving data...")
    _run_git_command(["stash"])
    _run_git_command(["pull"])
    _run_git_command(["stash", "pop"])
    _run_git_command(["add", "data/*.json"])
    _run_git_command(["commit", "-m", "[ci skip] data for admin migration run"])
    _run_git_command([
        "remote",
        "set-url",
        "--push",
        "origin",
        "https://%s@github.com/"
        "conda-forge/admin-migrations.git" % os.environ["GITHUB_TOKEN"],
    ])
    _run_git_command(["push"])


def run_migrators(feedstock, migrators):
    if len(migrators) == 0:
        return False

    if all(m.skip(feedstock) for m in migrators):
        return False

    pushed = False

    migrators_to_record = []

    feedstock_http = "https://%s@github.com/conda-forge/%s-feedstock.git" % (
        os.environ["GITHUB_TOKEN"],
        feedstock,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with pushd(tmpdir):
            _run_git_command(["clone", feedstock_http])

            with pushd("%s-feedstock" % feedstock):
                _run_git_command([
                    "remote",
                    "set-url",
                    "--push",
                    "origin",
                    feedstock_http,
                ])

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
                        _run_git_command([
                            "commit",
                            "-m",
                            "[ci skip] [skip ci] [cf admin skip] "
                            "***NO_CI*** %s" % m.message(),
                        ])
                        _run_git_command(["push"])
                        pushed = True
                    if worked:
                        migrators_to_record.append(m)

                    print(" ")

    for m in migrators_to_record:
        m.record(feedstock)

    return pushed


def main():
    migrators = [AutomergeAndRerender()]

    feedstocks = _load_feedstock_data()
    current_num = feedstocks["current"]
    next_num = (current_num + 1) % 2

    num_done_prev = sum(v == next_num for v in feedstocks["feedstocks"].values())

    num_done = 0
    num_pushed = 0
    start_time = time.time()
    for f in feedstocks["feedstocks"]:
        # out of time?
        if time.time() - start_time > MAX_SECONDS:
            break

        # did too many?
        if num_pushed >= MAX_MIGRATE:
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

        if not _repo_is_archived(f):
            pushed = run_migrators(f, migrators)
            if pushed:
                num_pushed += 1
        else:
            print("skipping archived feedstock")
            print(" ")
        feedstocks["feedstocks"][f] = next_num
        num_done += 1

        print("took %s seconds" % (time.time() - _start))
        print("on %d out of %d feedstocks" % (
            num_done_prev + num_done,
            len(feedstocks["feedstocks"]),
        ))
        print("migrated %d feedstokcs" % num_done)
        print("pushed to %d feedstocks" % num_pushed)
        elapsed_time = time.time() - start_time
        print("can migrate ~%d more feedstocks for this CI run" % (
            int(num_done / elapsed_time * (MAX_SECONDS - elapsed_time))
        ))

        print(" ")

    if all(v == next_num for v in feedstocks["feedstocks"].values()):
        print("processed all feedstocks - starting over!")
        feedstocks["current"] = next_num

    with open("data/feedstocks.json", "w") as fp:
        json.dump(feedstocks, fp)

    _commit_data()
