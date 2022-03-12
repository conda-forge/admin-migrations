#!/usr/bin/env bash

for slug in outputs; do
  upper_slug=$(echo "$slug" | tr '[:lower:]' '[:upper:]')
  rm -rf feedstock-${slug}
  git clone --quiet https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/feedstock-${slug}.git
  export FEEDSTOCK_${upper_slug}_REPO=`pwd`/feedstock-${slug}
  pushd feedstock-${slug}
  git remote set-url --push origin https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/feedstock-${slug}.git
  popd
done
