import os
import json
import time
import tempfile
import contextlib
import subprocess
import requests
import functools
import datetime

from requests.exceptions import RequestException
import github
import tqdm
import ruamel.yaml

from admin_migrations.migrators import (
    AppveyorForceDelete,
    RAutomerge,
    TeamsCleanup,
    CFEP13TokenCleanup,
    TravisCIAutoCancelPRs,
    # these are finished or not used so we don't run them
    # CondaForgeAutomerge,
    # CFEP13TokensAndConfig,
    # AppveyorDelete,
    # AutomergeAndRerender,
    # CFEP13TurnOff,
    # AutomergeAndBotRerunLabels,
)


def _assert_at_0():
    yaml = ruamel.yaml.YAML()
    with open(".github/workflows/migrate.yml", "r") as fp:
        _cfg = yaml.load(fp.read())
    ctab = _cfg["on"]["schedule"][0]["cron"]
    assert ctab == "0 * * * *", "Wrong cron tab %s for GHA!" % ctab


_assert_at_0()

DEBUG = "DEBUG_ADMIN_MIGRATIONS" in os.environ

if DEBUG:
    MAX_MIGRATE = 1
    MAX_SECONDS = 50 * 60
else:
    MAX_MIGRATE = 500
    MAX_SECONDS = min(50, max(60 - datetime.datetime.now().minute - 6, 0)) * 60


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


def _run_git_command(args, capture=False, check=True):
    if capture:
        subprocess.run(
            ['git'] + args,
            check=check,
        )
        return None
    else:
        s = subprocess.run(
            ['git'] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=check,
        )
        return s.returncode == 0, s.stdout.decode("utf-8")


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
            _branch = line.strip()[len("origin/"):]
            if line.strip()[len("origin/"):] != "master":
                branches.append(_branch)
    return ["master"] + branches


def _get_all_feedstocks():
    gh = github.Github(os.environ['GITHUB_TOKEN'], per_page=100)
    org = gh.get_organization("conda-forge")
    archived = set()
    not_archived = set()
    repos = org.get_repos(type='public')
    for r in tqdm.tqdm(repos, total=org.public_repos, desc='getting all feedstocks'):
        if r.name.endswith("-feedstock"):
            # special casing for weird renaming in the api
            if r.name == "numpy-sugar-feedstock":
                name = "numpy_sugar-feedstock"
            else:
                name = r.name

            if r.archived:
                archived.add(name[:-len("-feedstock")])
            else:
                not_archived.add(name[:-len("-feedstock")])

    return {"active": sorted(list(not_archived)), "archived": sorted(list(archived))}


def _load_feedstock_data():
    curr_hour = datetime.datetime.utcnow().hour
    if (
        (curr_hour % 2 == 0 or not os.path.exists("data/all_feedstocks.json"))
        and not DEBUG
    ):
        dt = time.time()
        all_feedstocks = _get_all_feedstocks()
        dt = time.time() - dt
        print(" ")

        # we run a bit less since this takes a few minutes
        global MAX_SECONDS
        MAX_SECONDS -= dt

        with open("data/all_feedstocks.json", "w") as fp:
            json.dump(all_feedstocks, fp, indent=2)
    else:
        print("using cached feedstock list")
        print(" ")
        with open("data/all_feedstocks.json", "r") as fp:
            all_feedstocks = json.load(fp)

    feedstocks = all_feedstocks["active"]

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
    _run_git_command(["pull", "--quiet"])
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
    _run_git_command(["push", "--quiet"])


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
            try:
                # use a full depth clone since some migrators rely on
                # having all of the branches
                _run_git_command(["clone", "--quiet", feedstock_http])
            except subprocess.CalledProcessError:
                print("    clone failed!")
                return made_api_calls

            with pushd("%s-feedstock" % feedstock):
                if (
                    os.path.exists("recipe/meta.yaml")
                    or os.path.exists("recipe/recipe/meta.yaml")
                ):
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

                            try:
                                print("    branch:", branch)
                                try:
                                    _run_git_command(
                                        ["switch", branch],
                                        capture=True,
                                        check=True,
                                    )
                                except Exception:
                                    ok, e = _run_git_command(
                                        [
                                            "checkout",
                                            "-b", branch,
                                            "-t", "origin/" + branch
                                        ],
                                        capture=True,
                                        check=False,
                                    )
                                    if not ok:
                                        raise RuntimeError(
                                            "git branch checkout error: %s" % e
                                        )

                                if m.skip(feedstock, branch):
                                    continue

                                worked, commit_me, made_api_calls = m.migrate(
                                    feedstock, branch)

                                if commit_me:
                                    _run_git_command([
                                        "commit",
                                        "--allow-empty",
                                        "-am",
                                        "[ci skip] [skip ci] [cf admin skip] "
                                        "***NO_CI*** %s" % m.message(),
                                    ])

                                    made_api_calls = True
                                    is_archived = _repo_is_archived(feedstock)
                                    if is_archived is not None:
                                        if not is_archived:
                                            _run_git_command(["push", "--quiet"])
                                        else:
                                            print("not pushing to archived feedstock")
                                    else:
                                        print(
                                            "could not get repo archived status - "
                                            "punting to next round"
                                        )

                            except Exception as e:
                                worked = False
                                print("    ERROR:", repr(e))

                            if worked:
                                migrators_to_record.append((m, branch))

                            print(" ")

    print("migration took %s seconds\n" % (time.time() - _start))

    for m, branch in migrators_to_record:
        m.record(feedstock, branch)

    return made_api_calls


def main():
    migrators = [
        AppveyorForceDelete(),
        RAutomerge(),
        TeamsCleanup(),
        CFEP13TokenCleanup(),
        TravisCIAutoCancelPRs(),
        # these are finished or not used so we don't run them
        # CondaForgeAutomerge(),
        # CFEP13TokensAndConfig(),
        # AppveyorDelete(),
        # AutomergeAndRerender(),
        # CFEP13TurnOff(),
        # AutomergeAndBotRerunLabels(),
    ]
    print(" ")

    feedstocks = _load_feedstock_data()
    current_num = feedstocks["current"]
    next_num = (current_num + 1) % 2

    num_done_prev = sum(v == next_num for v in feedstocks["feedstocks"].values())

    if DEBUG:
        # set DEBUG_ADMIN_MIGRATIONS in your env to enable this
        all_feedstocks = [
            "cf-autotick-bot-test-package",
        ]
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
