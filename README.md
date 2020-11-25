This repository is designed to gather tools needs to run different performance
tests. A number of git projects are installed as submodules in the `repos`
directory.


Before using any of the tooling update the submodules and create the python
virtual environments:

```
./init.sh
```

To use rally:

```
cd rally
./install_rally.sh
```

PerfKit with:

```
cd perfkitbenchmarker
export vm_http_proxy=<A HTTP PROXY>
export vm_https_proxy=<A HTTPS PROXY>
./example.sh
```

Openstack Clients:

```
source client_venv 
source openrc 
```

Add sriov ports to application

```
source zaza_venv 
./manage-sriov-ports.py --application ubuntu --network stor9 --vnic-binding-type direct add
```

Using scripts with Magpie

```
juju config magpie push-gateway=10.246.114.60
source client_venv 
./manage-sriov-ports.py --application magpie  --network stor9 --vnic-binding-type direct add
./manage-magpie-units.py -c 10.9.0.0/16 -l 10 -a magpie listen
./manage-magpie-units.py -a magpie advertise
juju run-action magpie/4 run-iperf network-cidr='10.9.0.0/16' units='magpie/3 magpie/2' iperf-batch-time=5 concurrency-progression='4 8' total-run-time=60 tag='special-run'
```
