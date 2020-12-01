#!/usr/bin/env python3

import asyncio
import argparse
import logging
import os
import sys
import subprocess
import tenacity
import textwrap
import tempfile
import time
from pathlib import Path
import yaml
import novaclient
import zaza.model
import zaza.utilities.cli as cli_utils
import zaza.openstack.utilities.openstack as zaza_os

MACHINE_PREFIX = "ps5-bench"
CONTROLLER_NAME = "{}-controller".format(MACHINE_PREFIX)
CLOUD_NAME = "{}-manual".format(MACHINE_PREFIX)


def get_network(neutron_client, network_name):
    """Return network that matches name.

    :param neutron_client: Neutron client
    :type neutron_client: neutronclient.v2_0.client.Client
    :param network_name: Name of network
    :type network_name: Str
    :returns: Network
    :rtype: Dict
    """
    networks = neutron_client.list_networks(name=network_name)['networks']
    assert len(networks) == 1, "ERROR: {} networks found".format(len(networks))
    return networks[0]


def get_port(neutron_client, port_name):
    """Return port that matches name.

    :param neutron_client: Neutron client
    :type neutron_client: neutronclient.v2_0.client.Client
    :param port_name: Name of port
    :type port_name: Str
    :returns: Port
    :rtype: Dict
    """
    port = None
    existing_ports = neutron_client.list_ports(name=port_name)['ports']
    if existing_ports:
        assert len(existing_ports) == 1, "ERROR: {} ports found".format(
            len(existing_ports))
        port = existing_ports[0]
    return port


def get_port_name(network, machine):
    """Return expected port name

    :param network: Dict of network data
    :param network: Dict
    :type machine: juju.machine.Machine
    :type machine: juju.machine.Machine
    :returns: Port name
    :rtype: str
    """
    return 'sriov_{}_{}'.format(network['name'], machine.entity_id)


def is_port_attached(nova_client, server, port_id):
    """Whether port with given id is attached to server

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    :param server: Server to check for port.
    :type servr: novaclient.v2.servers.Server
    :param port_id: Id of port to check
    :type port_id: str
    :returns: Whether port is attached
    :rtype: bool
    """
    for interface in server.interface_list():
        if interface.port_id == port_id:
            return True
    return False


def cleanup(nova_client, neutron_client, network_name, application_name):
    """Remove ports from servers and delete.

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    :param neutron_client: Neutron client
    :type neutron_client: neutronclient.v2_0.client.Client
    :param network_name: Name of network
    :type network_name: Str
    :param application_name: Name of application
    :type application_name: Str
    """
    network = get_network(neutron_client, network_name)
    for machine in zaza.model.get_machines(application_name=application_name):
        port_name = get_port_name(network, machine)
        port = get_port(neutron_client, port_name)
        if port:
            server = nova_client.servers.get(machine.data['instance-id'])
            if is_port_attached(nova_client, server, port['id']):
                logging.info("Removing port {} from {}".format(
                    port_name,
                    machine.data['instance-id']))
                server.interface_detach(port_id=port['id'])
            logging.info("Deleting port {}".format(port_name))
            neutron_client.delete_port(port['id'])


def add_port_to_netplan(neutron_client, network_name, application_name):
    units = {u.data['machine-id']: u.entity_id
             for u in zaza.model.get_units(application_name=application_name)}
    # Fold back into zaza.openstack.utilities.openstack
    network = get_network(neutron_client, network_name)
    for machine in zaza.model.get_machines(application_name=application_name):
        unit_name = units[machine.entity_id]
        port_name = get_port_name(network, machine)
        port = get_port(neutron_client, port_name)
        mac_address = port['mac_address']
        run_cmd_nic = "ip -f link -br -o addr|grep {}".format(mac_address)
        logging.info("Running '{}' on {}".format(run_cmd_nic, unit_name))
        interface = zaza.model.run_on_unit(unit_name, run_cmd_nic)
        interface = interface['Stdout'].split(' ')[0]

        run_cmd_netplan = """sudo egrep -iR '{}|{}$' /etc/netplan/
                            """.format(mac_address, interface)

        logging.info("Running '{}' on {}".format(run_cmd_netplan, unit_name))
        netplancfg = zaza.model.run_on_unit(unit_name, run_cmd_netplan)

        if (mac_address in str(netplancfg)) or (interface in str(netplancfg)):
            logging.warn("mac address {} or nic {} already exists in "
                         "/etc/netplan".format(mac_address, interface))
            continue
        body_value = textwrap.dedent("""\
            network:
                ethernets:
                    {0}:
                        dhcp4: true
                        dhcp6: false
                        optional: true
                        match:
                            macaddress: {1}
                        set-name: {0}
                version: 2
        """.format(interface, mac_address))
        for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_exponential(
                multiplier=1, min=2, max=10)):
            with attempt:
                with tempfile.NamedTemporaryFile(mode="w") as netplan_file:
                    netplan_file.write(body_value)
                    netplan_file.flush()
                    logging.info("Copying {} to {}".format(
                        unit_name,
                        '/home/ubuntu/60-dataport.yaml'))
                    subprocess.check_call([
                        'juju',
                        'scp',
                        netplan_file.name,
                        '{}:/home/ubuntu/60-dataport.yaml'.format(unit_name)])
                run_cmd_mv = ("sudo mv /home/ubuntu/60-dataport.yaml "
                              "/etc/netplan/")
                logging.info(
                    "Running '{}' on {}".format(run_cmd_mv, unit_name))
                zaza.model.run_on_unit(unit_name, run_cmd_mv)
                logging.info("Running netplan apply")
                zaza.model.run_on_unit(unit_name, "sudo netplan apply")


def create_ports(nova_client, neutron_client, network_name, application_name,
                 vnic_type, port_security_enabled=True, shutdown_move=True):
    """Add ports to all units in application.

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    :param neutron_client: Neutron client
    :type neutron_client: neutronclient.v2_0.client.Client
    :param network_name: Name of network
    :type network_name: Str
    :param application_name: Name of application
    :type application_name: Str
    :param vnic_type: vnic type
    :type vnic_type: Union[str, None]
    :param port_security_enabled: Whether to enable port security
    :type port_security_enabled: bool
    """
    network = get_network(neutron_client, network_name)
    for machine in zaza.model.get_machines(application_name=application_name):
        port_name = get_port_name(network, machine)
        port = get_port(neutron_client, port_name)
        if port:
            logging.warning("Skipping creating port {}".format(port_name))
        else:
            logging.info("Creating port {}".format(port_name))
            port_config = {
                'port': {
                    'admin_state_up': True,
                    'name': port_name,
                    'network_id': network['id'],
                    'port_security_enabled': port_security_enabled,
                }
            }
            if vnic_type:
                port_config['port']['binding:vnic_type'] = vnic_type
                port_config['port']['binding:profile'] = {
                    'capabilities': 'switchdev'}
            port = neutron_client.create_port(body=port_config)['port']
        server = nova_client.servers.get(machine.data['instance-id'])
        if is_port_attached(nova_client, server, port['id']):
            logging.warning(
                "Skipping attaching port {} to {}, already attached".format(
                     port_name,
                     machine.data['instance-id']))
        else:
            logging.info("Shutting down {}".format(
                machine.data['instance-id']))
            server_state = getattr(server, 'OS-EXT-STS:vm_state').lower()
            if shutdown_move and server_state != 'stopped':
                server.stop()
                #subprocess.call(
                #    ['juju', 'ssh', unit.unit_name, 'sudo shutdown -h now'])
                zaza_os.resource_reaches_status(
                    nova_client.servers,
                    server.id,
                    resource_attribute='OS-EXT-STS:vm_state',
                    expected_status="stopped",
                    msg="Server stopped")
            logging.info("Attaching port {} to {}".format(
                port_name,
                machine.data['instance-id']))
            server.interface_attach(
                port_id=port['id'],
                net_id=None,
                fixed_ip=None)
            logging.info("Starting up {}".format(
                machine.data['instance-id']))
            if shutdown_move:
                server.start()
                zaza_os.resource_reaches_status(
                    nova_client.servers,
                    server.id,
                    resource_attribute='OS-EXT-STS:vm_state',
                    expected_status='active',
                    msg="Server start")


def add_servers(nova_client, neutron_client, network_name, number_of_units,
                flavor_name, image_name, vnic_type='direct',
                port_security_enabled=False):
    """Create a servers using pre-created ports

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    :param neutron_client: Neutron client
    :type neutron_client: neutronclient.v2_0.client.Client
    :param network_name: Name of network
    :type network_name: Str
    :param number_of_units: Number of servers to create
    :type number_of_units: int
    :param flavor_name: Flavor to use for servers
    :type flavor_name: Str
    :param image_name: Image to use for servers
    :type image_name: Str
    :param vnic_type: vnic type
    :type vnic_type: Union[str, None]
    :param port_security_enabled: Whether to enable port security
    :type port_security_enabled: bool
    """
    network = get_network(neutron_client, network_name)

    image = nova_client.glance.find_image(image_name)

    flavor = nova_client.flavors.find(name=flavor_name)

    net = neutron_client.find_resource("network", network_name)
    meta = {}

    # Add ~/.ssh/id_rsa.pub if its not there already
    ssh_dir = '{}/.ssh'.format(str(Path.home()))
    keypair_name = 'ps5benchmarking'

    existing_keys = nova_client.keypairs.findall(name=keypair_name)
    key_file = '{}/id_rsa.pub'.format(ssh_dir, keypair_name)

    assert os.path.isfile(key_file), "Cannot find keyfile {}".format(key_file)

    if not existing_keys:
        with open(key_file, 'r') as kf:
            pub_key = kf.read()
        nova_client.keypairs.create(
            name=keypair_name,
            public_key=pub_key)

    for i in range(0, int(number_of_units)):
        if i == 0:
            vm_name = CONTROLLER_NAME
        else:
            vm_name = "{}-{}".format(MACHINE_PREFIX, i)

        try:
            nova_client.servers.find(name=vm_name)
            logging.warn("{} already exists, skipping".format(vm_name))
            continue
        except novaclient.exceptions.NotFound:
            pass
        port_name = "{}_port".format(vm_name)

        port_config = {
            'port': {
                'admin_state_up': True,
                'name': port_name,
                'network_id': net['id'],
                'port_security_enabled': port_security_enabled,
            }
        }
        if vnic_type:
            port_config['port']['binding:vnic_type'] = vnic_type
            port_config['port']['binding:profile'] = {
                'capabilities': 'switchdev'}
        port = neutron_client.create_port(body=port_config)['port']

        nics = [{'port-id': port.get('id')}]

        bdmv2 = None

        logging.info('Launching instance {}'.format(vm_name))
        instance = nova_client.servers.create(
            name=vm_name,
            image=image,
            block_device_mapping_v2=bdmv2,
            flavor=flavor,
            key_name=keypair_name,
            meta=meta,
            nics=nics)


def add_new_hostkey(ip):
    """Remove the existing hostkey and blindly add new one.

    :param ip: IP address entry to refresh
    :type ip: str
    """
    subprocess.check_call(
        ['ssh-keygen', '-R', ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT)
    conn = 'ubuntu@{}'.format(ip)
    subprocess.check_call(
        ['ssh', '-o', 'StrictHostKeyChecking=accept-new', conn, '"exit"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT)


def add_cloud(nova_client):
    """Register a manual cloud

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    """
    controller = nova_client.servers.find(name=CONTROLLER_NAME)
    ip = [ips[0] for net, ips in controller.networks.items()][0]
    unit_address = 'ubuntu@{}'.format(ip)
    add_new_hostkey(ip)
    clouds = yaml.load(
        subprocess.check_output(['juju', 'list-clouds', '--format', 'yaml']),
        Loader=yaml.FullLoader)
    if CLOUD_NAME in clouds:
        logging.warn('Cloud {} already exists'.format(CLOUD_NAME))
    else:
        contents = textwrap.dedent("""\
            clouds:
              {}:
                type: manual
                endpoint: {}
                regions:
                  default: {{}}
        """.format(CLOUD_NAME, unit_address))
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tfile:
            tfile.write(contents)
            logging.info(tfile.name)
        subprocess.check_output(
            ['juju', 'add-cloud', '--client', CLOUD_NAME, tfile.name])
    subprocess.check_output(
        ['juju', 'bootstrap', CLOUD_NAME, '{}-controller'.format(CLOUD_NAME)])


def add_machines(nova_client):
    """Add machines to manual cloud

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    """
    ips = []
    for server in nova_client.servers.list():
        if (server.name.startswith(MACHINE_PREFIX) and
                not server.name == CONTROLLER_NAME):
            ip = [ips[0] for net, ips in server.networks.items()][0]
            ips.append(ip)
            add_new_hostkey(ip)

    async def _add_machines():
        async def run_add_machine(ip):
            logging.info('Adding {}'.format(ip))
            cmd = ['juju', 'add-machine', 'ssh:ubuntu@{}'.format(ip)]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logging.error(
                    'Problem adding {}: {}'.format(ip,
                                                   stderr.decode().strip()))
            else:
                logging.info('Finished adding {}'.format(ip))
        await asyncio.gather(*[run_add_machine(ip) for ip in ips])
    asyncio.run(_add_machines())


def parse_args(args):
    """Parse command line arguments.

    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('action', help='Action to run: add or cleanup')
    parser.add_argument('-a', '--application', dest='application_name',
                        help='Name of Juju application to add port to',
                        required=False)
    parser.add_argument('-n', '--network', dest='network_name',
                        help='Name of network to create ports on',
                        required=False)
    parser.add_argument('-v', '--vnic-binding-type', dest='vnic_binding_type',
                        help='Vnic binding type: "direct" or "dummy')
    parser.add_argument('-u', '--number-of-units', dest='number_of_units',
                        help='Number of units')
    parser.add_argument('-f', '--flavor', dest='flavor',
                        help='Name of flavor')
    parser.add_argument('-i', '--image-name', dest='image_name',
                        help='Name of image')
    parser.add_argument('-p', '--enable-port-security',
                        dest='enable_port_security',
                        help='Whether to enable port security',
                        type=bool)
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(
        loglevel='INFO',
        vnic_binding_type='direct',
        enable_port_security=False)
    return parser.parse_args(args)


def main():
    args = parse_args(sys.argv[1:])
    cli_utils.setup_logging(log_level=args.loglevel.upper())
    session = zaza_os.get_undercloud_keystone_session()
    neutron_client = zaza_os.get_neutron_session_client(session)
    nova_client = zaza_os.get_nova_session_client(session)
    if args.vnic_binding_type == 'dummy':
        logging.warning('Running in dummy mode')
        binding_type = None
    else:
        binding_type = args.vnic_binding_type
    if args.action == 'cleanup':
        logging.info('Running cleanup')
        cleanup(
            nova_client,
            neutron_client,
            args.network_name,
            args.application_name)
    elif args.action == 'add-ports':
        logging.info('Adding ports')
        create_ports(
            nova_client,
            neutron_client,
            args.network_name,
            args.application_name,
            binding_type,
            shutdown_move=True)
        logging.info('Adding to netplan')
        add_port_to_netplan(
            neutron_client,
            args.network_name,
            args.application_name)
    elif args.action == 'add-servers':
        add_servers(
            nova_client,
            neutron_client,
            args.network_name,
            args.number_of_units,
            args.flavor,
            args.image_name,
            vnic_type=binding_type,
            port_security_enabled=args.enable_port_security)
    elif args.action == 'add-manual-cloud':
        add_cloud(nova_client)
    elif args.action == 'add-machines':
        add_machines(nova_client)


if __name__ == "__main__":
    main()
