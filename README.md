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

