# Dynamic inventory generation for Ansible 
Author: Giuseppe Paterno' gpaterno@gapterno.com
Derived from a script by lukas.pustina@codecentric.de

This Python script generates a dynamic inventory based on OpenStack instances
if passed without arguments.  

It is capable of setting ansible common variables (user and if to use sudo) 
and to set role(s) to given servers. These roles turns into group when 
passed to ansible.

The script is passed via "-i" to ansible-playbook. Ansible
Example:
ansible -i ./openstack_inventory.py all -m ping

## Usage
```
usage: openstack_inventory.py [-h] [--sudo] [--no-sudo] [--user USER]
                              [--no-user] [--role ROLE] [--no-roles] [--list]
                              [server [server ...]]

Process ansible inventory

positional arguments:
  server       openstack server instance

optional arguments:
  -h, --help   show this help message and exit
  --sudo       Turn on sudo in Ansible
  --no-sudo    Turn off sudo in Ansible
  --user USER  User used in Ansible to connect
  --no-user    Remove default user for host
  --role ROLE  Set role to server (can use multiple times)
  --no-roles   Delete all roles from server
  --list       List inventory
```


## Requirements
* Python: novaclient, openstackclient
* The environment variables OS_USERNAME, OS_PASSWORD, OS_TENANT_NAME, 
  OS_AUTH_URL must be set according to nova.

# Example metadata set
Set the metadata directly with the openstack client

```
openstack server set --property ansible_host_vars="ansible_ssh_user->centos;ansible_sudo->yes" instance_name
openstack server set --property roles="base,db" instance_name
```

