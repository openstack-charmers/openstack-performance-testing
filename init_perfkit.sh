#!/bin/bash -x

echo "Look away now"
cp perfkitbenchmarker/configs/default_config_constants.yaml .tox/perfkit/lib/python3.6/site-packages/perfkitbenchmarker/data/default_config_constants.yaml
cp perf-kit-patches/os_virtual_machine.py .tox/perfkit/lib/python3.6/site-packages/perfkitbenchmarker/providers/openstack/
cp perf-kit-patches/linux_virtual_machine.py .tox/perfkit/lib/python3.6/site-packages/perfkitbenchmarker/
