# admin-migrations
[![CircleCI](https://circleci.com/gh/conda-forge/admin-migrations.svg?style=svg)](https://circleci.com/gh/conda-forge/admin-migrations)

repo to run background admin migrations of conda-forge feedstocks

## How to Use this Repo

1. Write a script and put it in the `scripts` directory.
2. Add the script to the `.circleci/config.yml`.

CircleCI is set to run once an hour on a cron job.

## Guidelines and Ground Rules

1. Don't migrate more than ~100-200 feedstocks per hour.
2. Make sure to put `[ci skip] [skip ci] ***NO_CI***` in any commits to
   avoid massive rebuilds.
3. Test your migration first. The `https://github.com/conda-forge/cf-autotick-bot-test-package-feedstock`
   is available to help test migrations.
4. CircleCI has a `GITHUB_TOKEN` in the environment. Please do not exhaust this
   token's API requests.
5. Rate limit commits to feedstocks to at most a few per minute in order to reduce
   the load on our admin webservices.
