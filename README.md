# admin-migrations
[![tests](https://github.com/conda-forge/admin-migrations/actions/workflows/tests.yml/badge.svg)](https://github.com/conda-forge/admin-migrations/actions/workflows/tests.yml)
[![migrate](https://github.com/conda-forge/admin-migrations/actions/workflows/migrate.yml/badge.svg)](https://github.com/conda-forge/admin-migrations/actions/workflows/migrate.yml) [![pre-commit.ci status](https://results.pre-commit.ci/badge/github/conda-forge/admin-migrations/main.svg)](https://results.pre-commit.ci/latest/github/conda-forge/admin-migrations/main)

repo to run background admin migrations of conda-forge feedstocks

## How to Use this Repo

1. Write a subclass of `admin_migrations.base.Migrator`. You will need to
   fill out the `migrate` method. This method is called with the feedstock
   as the current working directory.
2. Add your migration class to the list in `admin_migrations.__main__.main`

GitHub actions is set to run once an hour on a cron job.

## Guidelines and Ground Rules

1. Don't migrate more than several hundred feedstocks per hour.
2. Make sure to put `[ci skip] [skip ci] [cf admin skip] ***NO_CI***` in any commits to
   avoid massive rebuilds.
3. Rate-limit commits to feedstocks to in order to reduce the load on our admin webservices.
4. Test your migration first. The `https://github.com/conda-forge/cf-autotick-bot-test-package-feedstock`
   is available to help test migrations.
5. GitHub actions has a `GITHUB_TOKEN` in the environment. Please do not exhaust this
   token's API requests.
6. Do not rerender feedstocks!

Items 1-3 are taken care of by the migrations code.

## Migration Progress

| migrator             | progress                                             | percent                   |
| -------------------- | ---------------------------------------------------- | :-----------------------: |
| CondaForgeYAMLTest   | *always runs*                                        |                         - |
| RAutomerge           | *always runs*                                        |                         - |
| RotateFeedstockToken | `##################                                ` |          37% (8733/23401) |
| TeamsCleanup         | *always runs*                                        |                         - |
