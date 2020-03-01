## Guidelines and Ground Rules

- [ ] Don't migrate more than ~100-200 feedstocks per hour.
- [ ] Make sure to put `[ci skip] [skip ci] [cf admin skip] ***NO_CI***` in any commits to
      avoid massive rebuilds.
- [ ] Test your migration first. The `https://github.com/conda-forge/cf-autotick-bot-test-package-feedstock`
      is available to help test migrations.
- [ ] CircleCI has a `GITHUB_TOKEN` in the environment. Please do not exhaust this
      token's API requests.
- [ ] Rate-limit commits to feedstocks to at most a few per minute in order to reduce
      the load on our admin webservices.
