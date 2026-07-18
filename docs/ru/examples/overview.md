**Language / Язык:** [English](../../examples/overview.md) | [Русский](overview.md)

# Обзор примеров клиентов

Исполняемые скрипты — в [`examples/`](../../../examples/).
Лаборатория покрытия API на Pulumi — в [`pulumi-tests/`](../../../pulumi-tests/).

## Краткая справка

| Path | Tool | Purpose |
|---|---|---|
| `examples/python/openstacksdk_cookbook.py` | openstacksdk | net + server + volume lifecycle |
| `examples/ansible/playbook.yml` | Ansible `uri` | минимальный Keystone/Nova/Neutron |
| `examples/terraform/main.tf` | Terraform | `openstack_compute_instance_v2` + volume |
| `examples/pulumi/` | Pulumi | `pulumi_openstack` Instance + Network |
| `examples/run_iac_stack.sh` | все четыре | последовательный smoke cookbook'ов |
| `pulumi-tests/` | Pulumi | каждая pack-операция × yoga→dalmatian + HTML-отчёт |

## Auth

1. `POST /v3/auth/tokens` → `X-Subject-Token`
2. Вызовы сервисов с `X-Auth-Token` на нужном [порту](../ports.md)

Лаборатория по умолчанию: `admin` / `secret`, проект `demo`, домен `Default`.

## Cookbook'и

- [Python (requests)](python-requests.md)
- [Python (openstacksdk)](python-openstacksdk.md)
- [Ansible](ansible.md)
- [Terraform](terraform.md)
- [Pulumi](pulumi.md)
- [CLI](openstack-cli.md)
- [Troubleshooting](troubleshooting-clients.md)

## Лаборатория покрытия API (Pulumi)

Полное руководство: [hypervisor-lab.md](../hypervisor-lab.md)

```bash
cd pulumi-tests
make up
make test-pulumi-smoke
make test-pulumi
open reports/pulumi-report.html
```

Probe-скрипты:

| Script | Purpose |
|---|---|
| `examples/python/openstack_smoke.py` | Multi-port GET smoke |
| `examples/python/openstack_surface_probe.py` | Pack operation probe (также используется Pulumi-лабой) |
