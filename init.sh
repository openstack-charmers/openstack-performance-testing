#!/bin/bash

[[ $(which python) == /usr/* ]] || { echo "In venv, aborting"; exit 1; }

git submodule init
git submodule update

( cd repos/charm-test-infra; tox -e clients; )
ln -fs repos/charm-test-infra/.tox/clients/bin/activate client_venv

( cd rally; tox -e rally; )
( cd rally; ln -fs ../repos/openstack-charm-testing/templates/rally rally-templates; )
( cd rally; ln -fs .tox/rally/bin/activate rally_venv; )

( cd perfkitbenchmarker; tox -e perfkit; )
( cd perfkitbenchmarker; ln -fs .tox/perfkit/bin/activate perfkit_venv; )

