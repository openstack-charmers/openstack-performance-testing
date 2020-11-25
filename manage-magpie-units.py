#!/usr/bin/env python3

import argparse
import collections
import copy
import logging
import subprocess
import sys
import time

import zaza.model
import zaza.utilities.cli as cli_utils
import zaza.utilities.juju as zaza_juju
import zaza.openstack.utilities.openstack as zaza_os
import novaclient.exceptions


Unit = collections.namedtuple('Unit', ['unit_name', 'server'])

def move(nova_client, unit, target_hypervisor):
    """Move a guest to a different hypervisor

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    :param unit: Unit to move
    :type unit: Unit
    :param target_hypervisor: Hypervisor to move unit to.
    :type target_hypervisor: str
    """
    logging.info("Stopping {} ({})".format(unit.unit_name, unit.server.id))
    if getattr(unit.server, 'OS-EXT-STS:vm_state').lower() != 'stopped':
        subprocess.call(
            ['juju', 'ssh', unit.unit_name, 'sudo shutdown -h now'])
        zaza_os.resource_reaches_status(
            nova_client.servers,
            unit.server.id,
            resource_attribute='OS-EXT-STS:vm_state',
            expected_status="stopped",
            msg="Server stopped")
    logging.info("Migrating {} ({}) to {} ".format(
        unit.unit_name,
        unit.server.id,
        target_hypervisor))
    try:
        unit.server.migrate(host=target_hypervisor)
        zaza_os.resource_reaches_status(
            nova_client.servers,
            unit.server.id,
            resource_attribute='OS-EXT-STS:vm_state',
            expected_status='resized',
            msg="Server moved")
        unit.server.confirm_resize()
    except novaclient.exceptions.BadRequest:
        logging.warn("Migration failed")
    zaza_os.resource_reaches_status(
        nova_client.servers,
        unit.server.id,
        resource_attribute='OS-EXT-STS:vm_state',
        expected_status='stopped',
        msg="Server stopped")
    logging.info("Starting {} ({})".format(unit.unit_name, unit.server.id))
    unit.server.start()
    zaza_os.resource_reaches_status(
        nova_client.servers,
        unit.server.id,
        resource_attribute='OS-EXT-STS:vm_state',
        expected_status='active',
        msg="Server stopped")


def get_placement(nova_client, application_name):
    """Find which hypervisor each unit is on.

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    :param application_name: Name of application
    :type application_name: Str
    :returns: Map of units on each hypervisor
    :rtype: Dict[str, List[Unit]]
    """
    unit_map = {h.hypervisor_hostname.split('.')[0]:[]
                for h in nova_client.hypervisors.list()}
    for machine in zaza.model.get_machines(application_name=application_name):
        server = nova_client.servers.get(machine.data['instance-id'])
        hypervisor = getattr(
            server,
            'OS-EXT-SRV-ATTR:hypervisor_hostname').split('.')[0]
        unt_name = zaza_juju.get_unit_name_from_host_name(
            server.name,
            application=application_name)
        unit_map[hypervisor].append(
            Unit(
                unt_name,
                server))
    return unit_map

def summary(nova_client, application_name):
    """Display which hypervisor each unit is on.

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    :param application_name: Name of application
    :type application_name: Str
    """
    placement = get_placement(nova_client, application_name)
    for hypervisor, units in placement.items():
        logging.info("{}: {}".format(
            hypervisor,
            ', '.join([u.unit_name for u in units])))

def balance(nova_client, application_name):
    """Move units onto hypervisor with no units.

    :param nova_client: Nova client
    :type nova_client: novaclient.v2.client.Client
    :param application_name: Name of application
    :type application_name: Str
    """
    placement = get_placement(nova_client, application_name)
    new_placement = {h:[] for h in placement.keys()}
    spares = []
    for hypervisor, units in placement.items():
        if len(units) > 1:
            spares.extend(units[1:])
    for hypervisor, units in placement.items():
        if len(units) == 0:
            try:
                new_placement[hypervisor].append(spares.pop())
            except IndexError as e:
                logging.warn("Run out of spares")
    for hypervisor, units in new_placement.items():
        for unit in units:
            logging.info("Move {} to {}".format(unit.unit_name, hypervisor))
            move(nova_client, unit, hypervisor)

def advertise(application_name):
    """Advertise ip addresses to peers.

    :param application_name: Name of application
    :type application_name: Str
    """
    for unit in zaza.model.get_units(application_name):
        zaza.model.run_action(unit.entity_id, 'advertise')

def listen(application_name, cidr, listner_count=10):
    """Advertise ip addresses to peers.

    :param application_name: Name of application
    :type application_name: Str
    """
    for unit in zaza.model.get_units(application_name):
        zaza.model.run_action(
            unit.entity_id,
            'listen',
            action_params={
                'network-cidr': cidr,
                'listner-count': listner_count})

def parse_args(args):
    """Parse command line arguments.

    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('action',
                        help='Action to run: add, cleanup, listen or advertise')
    parser.add_argument('-a', '--application', dest='application_name',
                        help='Name of Juju application to add port to',
                        required=True)
    parser.add_argument('-c', '--cidr', dest='cidr',
                        help='Network cidr to listen on',
                        required=False)
    parser.add_argument('-l', '--listeners', dest='listener_count',
                        help='Number of listeners',
                        required=False)
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(loglevel='INFO', vnic_binding_type='direct', listener_count=10)
    return parser.parse_args(args)


def main():
    args = parse_args(sys.argv[1:])
    cli_utils.setup_logging(log_level=args.loglevel.upper())
    #session = zaza_os.get_undercloud_keystone_session()
    #neutron_client = zaza_os.get_neutron_session_client(session)
    #nova_client = zaza_os.get_nova_session_client(session, version=2.56)
    if args.vnic_binding_type == 'dummy':
        logging.warn('Running in dummy mode')
        binding_type = None
    else:
        binding_type = args.vnic_binding_type
    if args.action == 'summary':
        logging.info('Running Summary')
        summary(
            zaza_os.get_nova_session_client(
                zaza_os.get_undercloud_keystone_session(),
                version=2.56),
            args.application_name)
    elif args.action == 'balance':
        logging.info('Running balance')
        balance(
            zaza_os.get_nova_session_client(
                zaza_os.get_undercloud_keystone_session(),
                version=2.56),
            args.application_name)
    elif args.action == 'advertise':
        logging.info('Running advertise')
        advertise(
            args.application_name)
    elif args.action == 'listen':
        logging.info('Running listen')
        listen(
            args.application_name,
            args.cidr,
            int(args.listener_count))


if __name__ == "__main__":
    main()
