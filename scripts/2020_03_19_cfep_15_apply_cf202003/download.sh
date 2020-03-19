#!/usr/bin/env bash

mkdir -p repodata
pushd repodata

for sd in  noarch linux-64 linux-armv7l linux-aarch64 linux-ppc64le osx-64 win-32 win-64; do
  echo ${sd}
  mkdir -p ${sd}

  pushd ${sd}

  mkdir -p web
  pushd web
  wget https://conda-web.anaconda.org/conda-forge/${sd}/repodata.json
  popd

  mkdir -p static
  pushd static
  wget https://conda-static.anaconda.org/conda-forge/${sd}/repodata.json
  popd
  
  popd
done

popd
