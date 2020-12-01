This repository is designed to gather tools needs to run different performance
tests. A number of git projects are installed as submodules in the `repos`
directory.

To create guests with direct network ports and then enlist them into juju:

1. Create machines on the given network:

```
$ ./manage-sriov-ports.py --network stor9 --number-of-units 10  --flavor m1.small --image-name focal --vnic-binding-type direct add-servers
2020-12-01 13:12:04 [INFO] AUTH_URL: http://10.245.161.156:5000/v3, api_ver: 3
2020-12-01 13:12:04 [INFO] Using keystone API V3 (or later) for undercloud auth
2020-12-01 13:12:04 [WARNING] Running in dummy mode
2020-12-01 13:12:06 [INFO] Launching instance ps5-bench-controller
2020-12-01 13:12:10 [INFO] Launching instance ps5-bench-1
2020-12-01 13:12:12 [INFO] Launching instance ps5-bench-2
2020-12-01 13:12:15 [INFO] Launching instance ps5-bench-3
2020-12-01 13:12:16 [INFO] Launching instance ps5-bench-4
2020-12-01 13:12:19 [INFO] Launching instance ps5-bench-5
2020-12-01 13:12:22 [INFO] Launching instance ps5-bench-6
2020-12-01 13:12:26 [INFO] Launching instance ps5-bench-7
2020-12-01 13:12:30 [INFO] Launching instance ps5-bench-8
2020-12-01 13:12:32 [INFO] Launching instance ps5-bench-9
```

1. Create manual cloud and bootstrap controller:

```
$ ./manage-sriov-ports.py add-manual-cloud
2020-12-01 13:14:00 [INFO] AUTH\_URL: http://10.245.161.156:5000/v3, api\_ver: 3
2020-12-01 13:14:00 [INFO] Using keystone API V3 (or later) for undercloud auth
Only clouds with registered credentials are shown.
There are more clouds, use --all to see them.
2020-12-01 13:14:03 [INFO] /tmp/tmpy\_llfnjk
Cloud "ps5-bench-manual" successfully added to your local client.
Creating Juju controller "ps5-bench-manual-controller" on ps5-bench-manual/default
Looking for packaged Juju agent version 2.8.6 for amd64
Installing Juju agent on bootstrap instance
Fetching Juju Dashboard 0.3.0
Running machine configuration script...
Bootstrap agent now started
Contacting Juju controller at 10.9.0.4 to verify accessibility...

Bootstrap complete, controller "ps5-bench-manual-controller" is now available
Controller machines are in the "controller" model
Initial model "default" added
(clients) ubuntu@gnuoy-bastio
```

1. Add pre-created machines to manual cloud:

```
$ ./manage-sriov-ports.py add-machines
2020-12-01 13:18:43 [INFO] AUTH\_URL: http://10.245.161.156:5000/v3, api\_ver: 3
2020-12-01 13:18:43 [INFO] Using keystone API V3 (or later) for undercloud auth
2020-12-01 13:18:59 [INFO] Adding 10.9.0.6
2020-12-01 13:18:59 [INFO] Adding 10.9.0.3
2020-12-01 13:18:59 [INFO] Adding 10.9.0.21
2020-12-01 13:18:59 [INFO] Adding 10.9.0.22
2020-12-01 13:18:59 [INFO] Adding 10.9.0.7
2020-12-01 13:18:59 [INFO] Adding 10.9.0.11
2020-12-01 13:18:59 [INFO] Adding 10.9.0.24
2020-12-01 13:18:59 [INFO] Adding 10.9.0.14
2020-12-01 13:18:59 [INFO] Adding 10.9.0.15
2020-12-01 13:20:01 [INFO] Finished adding 10.9.0.15
2020-12-01 13:20:03 [INFO] Finished adding 10.9.0.24
2020-12-01 13:20:03 [INFO] Finished adding 10.9.0.14
2020-12-01 13:20:03 [INFO] Finished adding 10.9.0.3
2020-12-01 13:20:08 [INFO] Finished adding 10.9.0.22
2020-12-01 13:20:20 [INFO] Finished adding 10.9.0.21
2020-12-01 13:20:21 [INFO] Finished adding 10.9.0.7
2020-12-01 13:20:24 [INFO] Finished adding 10.9.0.11
2020-12-01 13:20:34 [INFO] Finished adding 10.9.0.6
```


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
