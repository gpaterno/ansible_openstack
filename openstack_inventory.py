#!/usr/bin/env python
################################################################################
# Dynamic inventory generation for Ansible 
# Author: Giuseppe Paterno' gpaterno@gapterno.com
# Derived from a script by lukas.pustina@codecentric.de
# Released under the MIT License (MIT) 
#
# This Python script generates a dynamic inventory based on OpenStack instances.
# Check the included README.md
#
################################################################################

from __future__ import print_function
from novaclient import client
from openstackclient.common import utils
import os, sys, json
import argparse
import openstackclient
import novaclient


def main(args):
        parser = argparse.ArgumentParser(description='Process ansible inventory')
        parser.add_argument('server', nargs="*", default=None, help='openstack server instance')
        parser.add_argument('--sudo', action='store_true', default=None, help='Turn on sudo in Ansible')
        parser.add_argument('--no-sudo', action='store_true', default=None, help='Turn off sudo in Ansible')
        parser.add_argument('--user', default=None, help='User used in Ansible to connect')
        parser.add_argument('--no-user', action='store_true', default=None, help='Remove default user for host')
        parser.add_argument('--role', action='append', help='Set role to server (can use multiple times)')
        parser.add_argument('--no-roles', action='store_true', default=None, help='Delete all roles from server')
        parser.add_argument('--list', action='store_true', default=None, help='List inventory')
        values = parser.parse_args()

        # Setup novaclient
	credentials = getOsCredentialsFromEnvironment()

	nt = client.Client(credentials['VERSION'], 
                           credentials['USERNAME'], 
                           credentials['PASSWORD'], 
                           credentials['TENANT_NAME'], 
                           credentials['AUTH_URL'], 
                           service_type="compute")

        # If we have an option, proces tags
        if len(values.server) > 0:
           for server in values.server:
                try:
                   ostack_server = utils.find_resource(nt.servers, server)

                except openstackclient.common.exceptions.CommandError:
                   print("Server %s not found" % server)
                   sys.exit(1)

                # Set roles
                if values.role is not None and len(values.role) > 0:
                   nt.servers.set_meta_item(ostack_server, 'roles', ','.join(values.role))

                # Delete roles
                if values.no_roles:
                   try:
                      nt.servers.delete_meta(ostack_server, ['roles'])
                   except novaclient.exceptions.NotFound:
                      pass

                # Add sudo
                if values.sudo:
                    addAnsibleHostVar(nt, ostack_server, 'ansible_sudo', 'yes')

		# Delete sudo
		if values.no_sudo:
                    # Extract ansible_host_vars metadata and unpack it
                    deleteAnsibleHostVar(nt, ostack_server, 'ansible_sudo')

                # Add user
                if values.user is not None:
                    addAnsibleHostVar(nt, ostack_server, 'ansible_ssh_user', values.user)

                # remove user tags
                if values.no_user:
                    deleteAnsibleHostVar(nt, ostack_server, 'ansible_ssh_user')
                    

           sys.exit(0)

        # Invoking without parameter, let's dump
        # the inventory

	inventory = {}
	inventory['_meta'] = { 'hostvars': {} }

	for server in nt.servers.list():
		floatingIp = getFloatingIpFromServerForNetwork(server)
		if floatingIp:
			for group in getAnsibleHostGroupsFromServer(nt, server.id):
				addServerToHostGroup(group, floatingIp, inventory)
			host_vars = getAnsibleHostVarsFromServer(nt, server.id)
			if host_vars:
				addServerHostVarsToHostVars(host_vars, floatingIp, inventory)

	dumpInventoryAsJson(inventory)


## Delete an asible var from metadata
def deleteAnsibleHostVar(novaclient, server, variable):
   if 'ansible_host_vars' in server.metadata:
       host_vars_list = server.metadata['ansible_host_vars'].split(';')
       host_vars = {}

       for host_var_list in host_vars_list:
          key, value = host_var_list.split('->')
          host_vars[key] = value
   
       # If we have the var, let's put letete it
       if variable in host_vars:
          del host_vars[variable]

       # Delete the metadata if empty
       if len(host_vars) == 0:
          novaclient.servers.delete_meta(server, ['ansible_host_vars']) 
          return

       # pack again and set meta
       host_vars_list = []
       for key in host_vars.keys():
          host_vars_list.append("%s->%s" % (key, host_vars[key]))

       novaclient.servers.set_meta_item(server, 'ansible_host_vars', ';'.join(host_vars_list))

## Add an ansible var to metadata
def addAnsibleHostVar(novaclient, server, ansible_variable, ansible_value):
   host_vars = {}
   if 'ansible_host_vars' in server.metadata:
       host_vars_list = server.metadata['ansible_host_vars'].split(';')

       for host_var_list in host_vars_list:
          if host_var_list != '':
             key, value = host_var_list.split('->')
             host_vars[key] = value
   
   # Add variable
   host_vars[ansible_variable] = ansible_value

   # pack again and set meta
   host_vars_list = []
   for key in host_vars.keys():
      host_vars_list.append("%s->%s" % (key, host_vars[key]))

   novaclient.servers.set_meta_item(server, 'ansible_host_vars', ';'.join(host_vars_list))


def getOsCredentialsFromEnvironment():
	credentials = {}

        # Try to get Compute API version, otherwise default to v2
        if 'OS_COMPUTE_API_VERSION' in os.environ:
            credentials['VERSION'] = os.environ['OS_COMPUTE_API_VERSION']
        else:
            credentials['VERSION'] = "2"

	try:
		credentials['USERNAME'] = os.environ['OS_USERNAME']
		credentials['PASSWORD'] = os.environ['OS_PASSWORD']
		credentials['TENANT_NAME'] = os.environ['OS_TENANT_NAME']
		credentials['AUTH_URL'] = os.environ['OS_AUTH_URL']

	except KeyError as e:
		print("ERROR: environment variable %s is not defined" % e, file=sys.stderr)
		sys.exit(-1)

	return credentials

def getAnsibleHostGroupsFromServer(novaClient, serverId):
	metadata = getMetaDataFromServer(novaClient, serverId, 'roles')
	if metadata:
		return metadata.split(',')
	else:
		return ['default']

def getMetaDataFromServer(novaClient, serverId, key):
        try:
	   return novaClient.servers.get(serverId).metadata[key]
       
        except KeyError:
           return None

def getAnsibleHostVarsFromServer(novaClient, serverId):
	metadata = getMetaDataFromServer(novaClient, serverId, 'ansible_host_vars')
	if metadata:
		host_vars = {}
		for kv in metadata.split(';'):
			key, values = kv.split('->')
			if ',' in values:
                           values = values.split(',')
  
			host_vars[key] = values
		return host_vars
	else:
		return None

def getFloatingIpFromServerForNetwork(server):
        floating = None
        fixed = None

        # Assuming only one network for the host
        # extract floating if setted, otherwise return 
        # fixed IP as we're assuming a provider network or
        # a site-2-site VPN
	net = server.addresses.keys()[0]
        for addr in server.addresses[net]:
    
	   if addr['OS-EXT-IPS:type'] == 'floating':
              floating = addr['addr']

           if addr['OS-EXT-IPS:type'] == 'fixed':
              fixed = addr['addr']
 
        if floating is not None:
           return floating

        if floating is None and fixed is not None:
           return fixed

	return None

def addServerToHostGroup(group, floatingIp, inventory):
	host_group = inventory.get(group, {})
	hosts = host_group.get('hosts', [])
	hosts.append(floatingIp)
	host_group['hosts'] = hosts
	inventory[group] = host_group

def addServerHostVarsToHostVars(host_vars, floatingIp, inventory):
	inventory_host_vars = inventory['_meta']['hostvars'].get(floatingIp, {})
	inventory_host_vars.update(host_vars)
	inventory['_meta']['hostvars'][floatingIp] = inventory_host_vars

def dumpInventoryAsJson(inventory):
	print(json.dumps(inventory, indent=4))


if __name__ == "__main__":
	main(sys.argv)

