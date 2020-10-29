#!/bin/bash

[[ $(which python) == /usr/* ]] || { echo "In venv, aborting"; exit 1; }
git submodule init
git submodule update
( cd charm-test-infra; tox -e clients; )
tox -e rally,perfkit
ln -fs charm-test-infra/.tox/clients/bin/activate client_venv
ln -fs openstack-charm-testing/templates/rally rally-templates
ln -fs .tox/rally/bin/activate rally_venv
ln -fs .tox/perfkit/bin/activate perkit_venv
