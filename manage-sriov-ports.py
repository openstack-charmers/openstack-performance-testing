#!/usr/bin/env python3

import argparse
import logging
import sys
import subprocess
import tenacity
import textwrap
import tempfile

import zaza.model
import zaza.utilities.cli as cli_utils
import zaza.openstack.utilities.openstack as zaza_os


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
    units = {u.data['machine-id']: u.entity_id for u in zaza.model.get_units(application_name=application_name)}
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
                    logging.info("Copying {} to {}".format(unit_name, '/home/ubuntu/60-dataport.yaml'))
                    subprocess.check_call(['juju', 'scp', netplan_file.name, '{}:/home/ubuntu/60-dataport.yaml'.format(unit_name)])
                    #zaza.model.scp_to_unit(
                    #    unit_name, netplan_file.name,
                    #    '/home/ubuntu/60-dataport.yaml', user="ubuntu")
                run_cmd_mv = "sudo mv /home/ubuntu/60-dataport.yaml /etc/netplan/"
                logging.info("Running '{}' on {}".format(run_cmd_mv, unit_name))
                zaza.model.run_on_unit(unit_name, run_cmd_mv)
                logging.info("Running netplan apply")
                zaza.model.run_on_unit(unit_name, "sudo netplan apply")

def create_ports(nova_client, neutron_client, network_name, application_name,
                 vnic_type, port_security_enabled=True):
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
            logging.info("Attaching port {} to {}".format(
                port_name,
                machine.data['instance-id']))
            server.interface_attach(
                port_id=port['id'],
                net_id=None,
                fixed_ip=None)


def parse_args(args):
    """Parse command line arguments.

    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('action', help='Action to run: add or cleanup')
    parser.add_argument('-a', '--application', dest='application_name',
                        help='Name of Juju application to add port to',
                        required=True)
    parser.add_argument('-n', '--network', dest='network_name',
                        help='Name of network to create ports on',
                        required=True)
    parser.add_argument('-v', '--vnic-binding-type', dest='vnic_binding_type',
                        help='Vnic binding type: "direct" or "dummy')
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(loglevel='INFO', vnic_binding_type='direct')
    return parser.parse_args(args)


def main():
    args = parse_args(sys.argv[1:])
    cli_utils.setup_logging(log_level=args.loglevel.upper())
    session = zaza_os.get_undercloud_keystone_session()
    neutron_client = zaza_os.get_neutron_session_client(session)
    nova_client = zaza_os.get_nova_session_client(session)
    if args.vnic_binding_type == 'dummy':
        logging.warn('Running in dummy mode')
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
    elif args.action == 'add':
        logging.info('Adding ports')
        create_ports(
            nova_client,
            neutron_client,
            args.network_name,
            args.application_name,
            binding_type)
        logging.info('Adding to netplan')
        add_port_to_netplan(
            neutron_client,
            args.network_name,
            args.application_name)


if __name__ == "__main__":
    main()
