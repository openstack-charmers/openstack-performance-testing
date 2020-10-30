#!/bin/bash

[ -z $vm_http_proxy ] && { echo "WARNING: vm_http_proxy environment variable is not set"; }

source perfkit_venv
source ../openrc

pkb.py --cloud=OpenStack --machine_type=m1.small --benchmark_config_file=/home/ubuntu/bugs/openstack-perf-testing/perfkitbenchmarker/configs/os.yaml --openstack_network=private --benchmarks=iperf --os_type=ubuntu2004 --openstack_floating_ip_pool=ext_net --http_proxy=$vm_http_proxy --https_proxy=$vm_https_proxy
