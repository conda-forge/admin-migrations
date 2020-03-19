#!/usr/bin/env bash

cwd=`pwd`

rm -rf rerend-migrate
mkdir -p rerend-migrate
pushd rerend-migrate

# clone countyfair
git clone --depth=1 https://github.com/regro/cf-graph-countyfair.git

# now loop
start=`date +%s`
tot=`wc -l < cf-graph-countyfair/names.txt`
don=0
for name in `cat cf-graph-countyfair/names.txt | sort`; do
  if [[ `grep ${name} ${cwd}/admin-migrations/scripts/migrate_rerender_done.txt` == "${name}" ]]; then
    continue
  fi

  echo "================================================================================"
  echo "================================================================================"
  echo "================================================================================"
  echo $name

  git clone https://${GITHUB_TOKEN}@github.com/conda-forge/${name}-feedstock.git
  pushd ${name}-feedstock

  git remote set-url --push origin https://${GITHUB_TOKEN}@github.com/conda-forge/${name}-feedstock.git

  if [[ -f ".github/workflows/webservices.yml" ]] && [[ -f ".github/workflows/main.yml" ]]; then
    echo ${name} >> ${cwd}/admin-migrations/scripts/migrate_rerender_done.txt
  else
    mkdir -p .github/workflows/
    echo "\
on: repository_dispatch

jobs:
  webservices:
    runs-on: ubuntu-latest
    name: webservices
    steps:
      - name: webservices
        id: webservices
        uses: conda-forge/webservices-dispatch-action@master
        with:
          github_token: \${{ secrets.GITHUB_TOKEN }}" > .github/workflows/webservices.yml

    echo "\
on:
  status: {}
  check_suite:
    types:
      - completed

jobs:
  regro-cf-autotick-bot-action:
    runs-on: ubuntu-latest
    name: regro-cf-autotick-bot-action
    steps:
      - name: checkout
        uses: actions/checkout@v2
      - name: regro-cf-autotick-bot-action
        id: regro-cf-autotick-bot-action
        uses: regro/cf-autotick-bot-action@master
        with:
          github_token: \${{ secrets.GITHUB_TOKEN }}" > .github/workflows/main.yml

    git add .github/workflows/webservices.yml
    git add .github/workflows/main.yml
    git commit -m '[ci skip] [skip ci] [cf admin skip] ***NO_CI*** added webservices and automerge action configs'
    git push

    echo ${name} >> ${cwd}/admin-migrations/scripts/migrate_rerender_done.txt
  fi
  popd
  rm -rf ${name}-feedstock

  curr_time=`date +%s`
  don=$((don + 1))
  eta=`bc <<< "scale=1; (${curr_time} - ${start}) / ${don} * ($tot - $don)"`
  echo "done ${don} out of ${tot} - eta ${eta}"

  echo " "

  # sleep to rate limit loads on our admin web services
  sleep 15

  # limit to XYZ per hour
  if [[ ${don} == "2" ]]; then
    break
  fi
done

popd
rm -rf rerend-migrate

pushd ${cwd}/admin-migrations
git add scripts/migrate_rerender_done.txt
git commit -m 'added migrated repos for automerge and webservices'

git remote set-url --push origin https://${GITHUB_TOKEN}@github.com/conda-forge/admin-migrations.git
git push

popd
