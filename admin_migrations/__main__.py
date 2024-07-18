import os
import json
import time
import tempfile
import contextlib
import subprocess
import requests
import functools
import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from requests.exceptions import RequestException
import github
import tqdm
import ruamel.yaml

from admin_migrations.migrators import (
    RAutomerge,
    TraviCINoOSXAMD64,
    CondaForgeAutomergeUpdate,
    CondaForgeYAMLTest,
    # these are finished or not used so we don't run them
    # RotateCFStagingToken,
    # RotateFeedstockToken,
    # CondaForgeMasterToMain,
    # FeedstocksServiceUpdate,
    # DotConda,
    # CondaForgeGHAWithMain,
    # CFEP13AzureTokenCleanup,
    # TeamsCleanup,
    # CFEP13TokenCleanup,
    # AppveyorForceDelete,
    # TravisCIAutoCancelPRs,
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
    if "schedule" in _cfg["on"]:
        ctab = _cfg["on"]["schedule"][0]["cron"]
        assert ctab == "0 * * * *", "Wrong cron tab %s for GHA!" % ctab


_assert_at_0()

DEBUG = "DEBUG_ADMIN_MIGRATIONS" in os.environ

if DEBUG:
    MAX_MIGRATE = 1
    MAX_SECONDS = 50 * 60
    MAX_WORKERS = 1
else:
    MAX_MIGRATE = 2000
    MAX_SECONDS = min(50, max(60 - datetime.datetime.now().minute - 6, 0)) * 60
    MAX_WORKERS = 2


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


def _run_git_command(args, check=True):
    s = subprocess.run(
        ['git'] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )
    if s.returncode != 0:
        print(f"    ERROR: {s.stdout.decode('utf-8')}", flush=True)
    return s.returncode == 0, s.stdout.decode("utf-8")


def _get_curr_branch():
    o = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return o.stdout.decode("utf=8").strip()


def _get_branches(default_branch):
    o = subprocess.run(
        ["git", "branch", "-r"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    branches = set()
    for line in o.stdout.decode("utf-8").split('\n'):
        if len(line) > 0 and "origin/HEAD" not in line:
            _branch = line.strip()[len("origin/"):]
            if _branch != default_branch:
                branches |= set([_branch])
    return [default_branch] + [br for br in branches]


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
        print(" ", flush=True)

        # we run a bit less since this takes a few minutes
        global MAX_SECONDS
        MAX_SECONDS -= dt

        with open("data/all_feedstocks.json", "w") as fp:
            json.dump(all_feedstocks, fp, indent=2)
    else:
        print("using cached feedstock list", flush=True)
        print(" ", flush=True)
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
    print("\nsaving data...", flush=True)
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
        "https://x-access-token:%s@github.com/"
        "conda-forge/admin-migrations.git" % os.environ["GITHUB_TOKEN"],
    ])
    _run_git_command(["push", "--quiet"])


def run_migrators(feedstock, migrators):
    if len(migrators) == 0:
        return False, []

    print("=" * 80, flush=True)
    print("=" * 80, flush=True)
    print("=" * 80, flush=True)
    print("migrating %s" % feedstock, flush=True)

    _start = time.time()

    made_api_calls = False

    # this will be a set of tuples with the migrator class and the branch
    migrators_to_record = []

    feedstock_http = \
        "https://x-access-token:%s@github.com/conda-forge/%s-feedstock.git" % (
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
                print("    clone failed!", flush=True)
                return made_api_calls, migrators_to_record

            with pushd("%s-feedstock" % feedstock):
                if (
                    os.path.exists("recipe/meta.yaml")
                    or os.path.exists("recipe/recipe/meta.yaml")
                    # This is a rattler-build recipe
                    or os.path.exists("recipe/recipe.yaml")
                ):
                    _run_git_command([
                        "remote",
                        "set-url",
                        "--push",
                        "origin",
                        feedstock_http,
                    ])

                    default_branch = _get_curr_branch()
                    branches = _get_branches(default_branch)

                    for m in migrators:
                        print("\nmigrator %s" % m.__class__.__name__, flush=True)

                        for branch in branches:
                            if branch != default_branch and m.main_branch_only:
                                continue

                            try:
                                print("    branch:", branch, flush=True)
                                try:
                                    _run_git_command(
                                        ["switch", branch],
                                        check=True,
                                    )
                                except Exception:
                                    ok, e = _run_git_command(
                                        [
                                            "checkout",
                                            "-b", branch,
                                            "-t", "origin/" + branch
                                        ],
                                        check=False,
                                    )
                                    if not ok:
                                        raise RuntimeError(
                                            "git branch checkout error: %s" % e
                                        )

                                if m.skip(feedstock, branch):
                                    continue

                                worked, commit_me, _made_api_calls = m.migrate(
                                    feedstock, branch)
                                made_api_calls = made_api_calls or _made_api_calls

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
                                            print(
                                                "not pushing to archived feedstock",
                                                flush=True,
                                            )
                                    else:
                                        print(
                                            "could not get repo archived status - "
                                            "punting to next round",
                                            flush=True,
                                        )

                            except Exception as e:
                                worked = False
                                print("    ERROR:", repr(e), flush=True)

                            if worked:
                                migrators_to_record.append((m, branch))

                            print(" ", flush=True)

    print("\nmigration took %s seconds\n\n" % (time.time() - _start), flush=True)

    return made_api_calls, migrators_to_record


def _report_progress(
    num_done_prev, num_done, feedstocks, num_pushed_or_apied, start_time
):
    print("on %d out of %d feedstocks" % (
        num_done_prev + num_done,
        len(feedstocks["feedstocks"]),
    ), flush=True)
    print("migrated %d feedstokcs" % num_done, flush=True)
    print(
        "pushed or made API calls for "
        "%d feedstocks" % num_pushed_or_apied, flush=True)
    elapsed_time = time.time() - start_time
    print("can migrate ~%d more feedstocks for this CI run" % (
        max(int(num_done / elapsed_time * (MAX_SECONDS - elapsed_time)), 0)
    ), flush=True)

    print(" ", flush=True)


def main():
    migrators = [
        RAutomerge(),
        TraviCINoOSXAMD64(),
        CondaForgeYAMLTest(),
        # these are finished or not used so we don't run them
        # RotateCFStagingToken(),
        # RotateFeedstockToken(),
        # CondaForgeMasterToMain(),  # this one always goes first since it makes extra
        #                            # commits etc
        # FeedstocksServiceUpdate(),
        CondaForgeAutomergeUpdate(),
        # DotConda(),
        # CondaForgeGHAWithMain(),
        # RotateCFStagingToken(),
        # RotateFeedstockToken(),
        # CFEP13AzureTokenCleanup(),
        # TeamsCleanup(),
        # CFEP13TokenCleanup(),
        # AppveyorForceDelete(),
        # TravisCIAutoCancelPRs(),
        # CondaForgeAutomerge(),
        # CFEP13TokensAndConfig(),
        # AppveyorDelete(),
        # AutomergeAndRerender(),
        # CFEP13TurnOff(),
        # AutomergeAndBotRerunLabels(),
    ]
    print(" ", flush=True)

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

    n_workers = min([m.max_processes for m in migrators])
    if n_workers <= 0:
        n_workers = os.environ.get("CPU_COUNT", MAX_WORKERS)
        try:
            n_workers = int(n_workers)
        except Exception:
            n_workers = MAX_WORKERS

    if n_workers <= 0:
        n_workers = MAX_WORKERS

    if DEBUG:
        n_workers = 1

    if n_workers > MAX_WORKERS:
        n_workers = MAX_WORKERS

    num_done = 0
    num_pushed_or_apied = 0
    start_time = time.time()
    report_time = time.time()
    futs = {}
    with ProcessPoolExecutor(max_workers=n_workers) as exec:
        for f in all_feedstocks:
            # did we do this one?
            if feedstocks["feedstocks"][f] != current_num:
                continue

            # migrate
            print(
                "\n# of feedstocks running|n_workers: %s|%s\n" % (
                    len(futs),
                    n_workers
                ),
                flush=True,
            )
            if len(futs) >= n_workers:
                for fut in as_completed(futs):
                    made_api_call, migrations_to_record = fut.result()
                    if made_api_call:
                        num_pushed_or_apied += 1
                    feedstocks["feedstocks"][futs[fut]] = next_num
                    num_done += 1

                    for _m, _branch in migrations_to_record:
                        _m.record(futs[fut], _branch)

                    print("\nfinished %s\n" % futs[fut], flush=True)

                    if time.time() - report_time > 10:
                        report_time = time.time()
                        _report_progress(
                            num_done_prev, num_done, feedstocks,
                            num_pushed_or_apied, start_time
                        )

                    break

                del futs[fut]

            fut = exec.submit(run_migrators, f, migrators)
            futs[fut] = f

            # out of time?
            if time.time() - start_time > MAX_SECONDS:
                break

            # did too many?
            if num_pushed_or_apied >= MAX_MIGRATE:
                break

    # clean up
    for fut in as_completed(futs):
        made_api_call, migrations_to_record = fut.result()
        if made_api_call:
            num_pushed_or_apied += 1
        feedstocks["feedstocks"][futs[fut]] = next_num
        num_done += 1

        for _m, _branch in migrations_to_record:
            _m.record(futs[fut], _branch)

        print("\nfinished %s\n" % futs[fut], flush=True)

    _report_progress(
        num_done_prev, num_done, feedstocks,
        num_pushed_or_apied, start_time
    )

    if all(v == next_num for v in feedstocks["feedstocks"].values()):
        print("=" * 80, flush=True)
        print("=" * 80, flush=True)
        print("=" * 80, flush=True)
        print("processed all feedstocks - starting over!", flush=True)
        feedstocks["current"] = next_num

    with open("data/feedstocks.json", "w") as fp:
        json.dump(feedstocks, fp, indent=2)

    if not DEBUG:
        _commit_data()
