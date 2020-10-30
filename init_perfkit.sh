#!/bin/bash -x

echo "Look away now"
BASE='.tox/perfkit/lib/python3.6/site-packages/perfkitbenchmarker'

cp perfkitbenchmarker/configs/default_config_constants.yaml ${BASE}/data/default_config_constants.yaml
cp perf-kit-patches/os_virtual_machine.py ${BASE}/providers/openstack/
cp perf-kit-patches/linux_virtual_machine.py ${BASE}/
cp perf-kit-patches/ssh_config.j2 ${BASE}/data/
cp perf-kit-patches/iperf.py ${BASE}/linux_packages/
