# admin-migrations
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
