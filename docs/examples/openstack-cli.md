**Language / Язык:** [English](openstack-cli.md) | [Русский](../ru/examples/openstack-cli.md)

# OpenStack CLI

```bash
export OS_AUTH_URL=http://127.0.0.1:5000/v3
export OS_USERNAME=admin
export OS_PASSWORD=secret
export OS_PROJECT_NAME=demo
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_DOMAIN_NAME=Default
export OS_IDENTITY_API_VERSION=3

openstack token issue
openstack server list
openstack network list
openstack volume list
openstack stack list
```
