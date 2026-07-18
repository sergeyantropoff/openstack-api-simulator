**Language / Язык:** [English](ansible.md) | [Русский](../ru/examples/ansible.md)

# Ansible (openstack.cloud)

## Cookbook (single stack)

[`examples/ansible/playbook.yml`](../../examples/ansible/playbook.yml) uses
`ansible.builtin.uri` against Keystone/Nova/Neutron/Glance — no Galaxy collections
required. Good for a minimal “create server + metadata + cleanup” walkthrough.

```bash
make up && make seed-demo
cd examples/ansible
ansible-playbook -i inventory.ini playbook.yml
```

Auth: `http://127.0.0.1:5000/v3`, user `admin`, password `secret`, project `demo`.

API coverage integration suites now live under [`pulumi-tests/`](../../pulumi-tests/)
(Pulumi / `pulumi_openstack`). See [hypervisor-lab.md](../hypervisor-lab.md).
