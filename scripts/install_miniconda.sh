#!/usr/bin/env bash
if [ ! -d ${HOME}/miniconda ]; then
  wget https://github.com/conda-forge/miniforge/releases/download/4.8.3-1/Miniforge3-Linux-x86_64.sh -O miniconda.sh
  bash miniconda.sh -b -p ${HOME}/miniconda
  rm -f miniconda.sh

  export PATH=${HOME}/miniconda/bin:$PATH

  conda config --set always_yes yes --set changeps1 no
  conda config --add channels defaults
  conda config --add channels conda-forge
  conda update -q conda
fi

export PATH=${HOME}/miniconda/bin:$PATH

conda config --set always_yes yes --set changeps1 no
conda config --add channels defaults
conda config --add channels conda-forge
conda update -q conda

source activate base

conda update --all -y -q

conda install -y -q --file requirements.txt

pip install --no-deps -e .

git config --global user.email "cf-blacksmithy@email.com"
git config --global user.name "cf-blacksmithy"
