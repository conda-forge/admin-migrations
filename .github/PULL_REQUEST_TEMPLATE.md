## Guidelines and Ground Rules

- [x] Don't migrate more than several hundred feedstocks per hour.
- [x] Make sure to put `[ci skip] [skip ci] [cf admin skip] ***NO_CI***` in any commits to
      avoid massive rebuilds.
- [x] Rate-limit commits to feedstocks to in order to reduce the load on our admin webservices.
- [ ] Test your migration first. The `https://github.com/conda-forge/cf-autotick-bot-test-package-feedstock` is available to help test migrations.
- [ ] GitHub actions has a `GITHUB_TOKEN` in the environment. Please do not exhaust this
       token's API requests.
- [ ] Do not rerender feedstocks!

Items 1-3 are taken care of by the migrations code assuming you don't make any significant changes.
