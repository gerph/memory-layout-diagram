#!/bin/bash
##
# Set up the packaging to produce a good release.
#

thisdir=$(cd "$(dirname "$0")" && pwd -P)

eval "$(${thisdir}/ci-vars --shell --repo "${thisdir}")"
version="${CI_BRANCH_VERSION//-dirty}"

if [[ "$version" =~ ^(.*)\.([a-z]*)\.([0-9]*)$ ]] ; then
    version="${BASH_REMATCH[1]}+${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
fi

rm -rf dist

cp setup.py setup-original.py
sed "s/version = '.*'/version = '$version'/" \
    < setup-original.py \
    > setup.py
python setup.py sdist
mv setup-original.py setup.py

rm -rf memory_layout.egg-info
