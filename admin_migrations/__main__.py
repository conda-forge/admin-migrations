import os
import json
import time
import tempfile
import contextlib
import subprocess
import requests
import functools

from requests.exceptions import RequestException

from admin_migrations.migrators import (
    AutomergeAndRerender,
    AppveyorDelete,
    # these are finished so we don't run them
    # AutomergeAndBotRerunLabels,
)

DEBUG = "DEBUG_ADMIN_MIGRATIONS" in os.environ

if DEBUG:
    MAX_MIGRATE = 1
    MAX_SECONDS = 50 * 60
else:
    MAX_MIGRATE = 1000
    MAX_SECONDS = 50 * 60


@functools.lru_cache(maxsize=20000)
def _get_repo_is_archived(feedstock):
    headers = {
        "authorization": "Bearer %s" % os.environ['GITHUB_TOKEN'],
        'content-type': 'application/json',
    }
    r = requests.get(
        "https://api.github.com/repos/conda-forge/%s-feedstock" % feedstock,
        headers=headers,
    )
    return r.json()["archived"]


def _repo_is_archived(feedstock):
    for _ in range(10):
        try:
            return _get_repo_is_archived(feedstock)
        except (json.JSONDecodeError, RequestException):
            pass
    return None

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


def _get_branches():
    o = subprocess.run(
        ["git", "branch", "-r"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    branches = []
    for line in o.stdout.decode("utf-8").split('\n'):
        if len(line) > 0 and "origin/HEAD" not in line:
            branches.append(line.strip()[len("origin/"):])
    return branches


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

    print("=" * 80)
    print("=" * 80)
    print("=" * 80)
    print("migrating %s" % feedstock)

    _start = time.time()

    made_api_calls = False

    # this will be a set of tuples with the migrator class and the branch
    migrators_to_record = []

    feedstock_http = "https://%s@github.com/conda-forge/%s-feedstock.git" % (
        os.environ["GITHUB_TOKEN"],
        feedstock,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with pushd(tmpdir):
            # use a full depth clone since some migrators rely on
            # having all of the branches
            _run_git_command(["clone", feedstock_http])

            with pushd("%s-feedstock" % feedstock):
                if os.path.exists("recipe/meta.yaml"):
                    _run_git_command([
                        "remote",
                        "set-url",
                        "--push",
                        "origin",
                        feedstock_http,
                    ])

                    branches = _get_branches()

                    for m in migrators:
                        print("\nmigrator %s" % m.__class__.__name__)

                        for branch in branches:
                            if branch != "master" and m.master_branch_only:
                                continue

                            print("    branch:", branch)
                            _run_git_command(["checkout", branch])

                            if m.skip(feedstock, branch):
                                continue
                            try:
                                worked, commit_me, made_api_calls = m.migrate(
                                    feedstock, branch)
                            except Exception:
                                worked = False
                                commit_me = False

                            if commit_me:
                                made_api_calls = True
                                is_archived = _repo_is_archived(feedstock)
                                if is_archived is not None:
                                    if not is_archived:
                                        _run_git_command([
                                            "commit",
                                            "-m",
                                            "[ci skip] [skip ci] [cf admin skip] "
                                            "***NO_CI*** %s" % m.message(),
                                        ])
                                        _run_git_command(["push"])
                                    else:
                                        print("not pushing to archived feedstock")
                                else:
                                    print(
                                        "could not get repo archived status - "
                                        "punting to next round"
                                    )

                            if worked:
                                migrators_to_record.append((m, branch))

                            print(" ")

    print("migration took %s seconds\n" % (time.time() - _start))

    for m, branch in migrators_to_record:
        m.record(feedstock, branch)

    return made_api_calls


def main():
    migrators = [
        AutomergeAndRerender(),
        AppveyorDelete(),
        # these are finished so we don't run them
        # AutomergeAndBotRerunLabels(),
    ]
    print(" ")

    feedstocks = _load_feedstock_data()
    current_num = feedstocks["current"]
    next_num = (current_num + 1) % 2

    num_done_prev = sum(v == next_num for v in feedstocks["feedstocks"].values())

    if DEBUG:
        all_feedstocks = ["cf-autotick-bot-test-package"]
        for fs in all_feedstocks:
            feedstocks["feedstocks"][fs] = current_num
        for m in migrators:
            for fs in all_feedstocks:
                if fs in m._done_table:
                    del m._done_table[fs]
    else:
        all_feedstocks = list(feedstocks["feedstocks"].keys())

    num_done = 0
    num_pushed_or_apied = 0
    start_time = time.time()
    report_time = time.time()
    for f in all_feedstocks:
        # out of time?
        if time.time() - start_time > MAX_SECONDS:
            break

        # did too many?
        if num_pushed_or_apied >= MAX_MIGRATE:
            break

        # did we do this one?
        if feedstocks["feedstocks"][f] != current_num:
            continue

        # migrate
        made_api_call = run_migrators(f, migrators)
        if made_api_call:
            num_pushed_or_apied += 1
        feedstocks["feedstocks"][f] = next_num
        num_done += 1

        if time.time() - report_time > 10:
            report_time = time.time()
            print("on %d out of %d feedstocks" % (
                num_done_prev + num_done,
                len(feedstocks["feedstocks"]),
            ))
            print("migrated %d feedstokcs" % num_done)
            print("pushed or made API calls for %d feedstocks" % num_pushed_or_apied)
            elapsed_time = time.time() - start_time
            print("can migrate ~%d more feedstocks for this CI run" % (
                int(num_done / elapsed_time * (MAX_SECONDS - elapsed_time))
            ))

            print(" ")

    if all(v == next_num for v in feedstocks["feedstocks"].values()):
        print("=" * 80)
        print("=" * 80)
        print("=" * 80)
        print("processed all feedstocks - starting over!")
        feedstocks["current"] = next_num

    with open("data/feedstocks.json", "w") as fp:
        json.dump(feedstocks, fp, indent=2)

    if not DEBUG:
        _commit_data()
