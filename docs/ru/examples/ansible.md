**Language / Язык:** [English](../../examples/ansible.md) | [Русский](ansible.md)

# Ansible (openstack.cloud)

## Cookbook (один stack)

[`examples/ansible/playbook.yml`](../../../examples/ansible/playbook.yml) —
`ansible.builtin.uri` против Keystone/Nova/Neutron/Glance.

```bash
make up && make seed-demo
cd examples/ansible
ansible-playbook -i inventory.ini playbook.yml
```

Auth: `http://127.0.0.1:5000/v3`, `admin` / `secret`, проект `demo`.

Интеграционное покрытие API теперь в [`pulumi-tests/`](../../../pulumi-tests/)
(Pulumi / `pulumi_openstack`). См. [hypervisor-lab.md](../hypervisor-lab.md).
