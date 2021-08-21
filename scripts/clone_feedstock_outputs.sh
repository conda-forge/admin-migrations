#!/usr/bin/env bash

rm -rf feedstock-outputs
git clone --quiet https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/feedstock-outputs.git
export FEEDSTOCK_OUTPUTS_REPO=`pwd`/feedstock-outputs
pushd feedstock-outputs
git remote set-url --push origin https://x-access-token:${GITHUB_TOKEN}@github.com/conda-forge/feedstock-outputs.git
popd
