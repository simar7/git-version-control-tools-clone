#!/bin/bash

if [ ! -e version-control-tools ]; then
  hg clone /version-control-tools version-control-tools
fi

cd version-control-tools
hg pull
hg --config extensions.purge= purge
hg up tip

# We always want to update BMO's source code as part of CI.
export FETCH_BMO=1

./create-test-environment
source venv/bin/activate
./run-mercurial-tests.py -j2 --all-versions --cover
result=$?

rm -rf /version-control-tools/coverage
mv coverage/ /version-control-tools/

# Generate Sphinx documentation.
make -C docs html
rm -rf /version-control-tools/sphinx-docs
mv docs/_build /version-control-tools/sphinx-docs

# Generate Python eggs for Review Board extensions.
rm -rf /version-control-tools/artifacts
mkdir -p /version-control-tools/artifacts/eggs
DOCKER_STATE_FILE=.docker-state.json testing/docker-control.py build-reviewboard-eggs /version-control-tools/artifacts/eggs

# Generate Mercurial RPMs.
mkdir -p /version-control-tools/artifacts/rpms
DOCKER_STATE_FILE=.docker-state.json testing/docker-control.py build-mercurial-rpms /version-control-tools/artifacts/rpms

# Ideally this would be part of running tests. Until then, add it here
# so Jenkins doesn't bloat.
DOCKER_STATE_FILE=.docker-state.json testing/docker-control.py prune-images

exit $result
