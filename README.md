After cloning init with:

```
./init.sh
```

Prepare ralley run with:

```
./install_rally.sh
```

PerfKit with:

```
source perfkit_venv
pkb.py --cloud=OpenStack --machine_type=m1.small --benchmark_config_file=/home/ubuntu/bugs/openstack-perf-testing/perfkitbenchmarker/configs/os.yaml --openstack_network=private --benchmarks=iperf --os_type=ubuntu1804 --openstack_floating_ip_pool=ext_net --http_proxy=$http_proxy --https_proxy=$https_proxy
```

Openstack Clients:

```
source client_venv 
source openrc 
```
