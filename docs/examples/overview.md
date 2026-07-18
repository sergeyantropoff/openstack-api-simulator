**Language / Язык:** [English](overview.md) | [Русский](../ru/examples/overview.md)

# Client examples overview

Runnable scripts live under [`examples/`](../../examples/).
Pulumi API coverage lab lives under [`pulumi-tests/`](../../pulumi-tests/).

## Quick reference

| Path | Tool | Purpose |
|---|---|---|
| `examples/python/openstacksdk_cookbook.py` | openstacksdk | net + server + volume lifecycle |
| `examples/ansible/playbook.yml` | Ansible `uri` | minimal Keystone/Nova/Neutron |
| `examples/terraform/main.tf` | Terraform | `openstack_compute_instance_v2` + volume |
| `examples/pulumi/` | Pulumi | `pulumi_openstack` Instance + Network |
| `examples/run_iac_stack.sh` | all four | sequential smoke of cookbooks |
| `pulumi-tests/` | Pulumi | every pack operation × yoga→dalmatian + HTML report |

## Auth quick reference

1. `POST /v3/auth/tokens` → `X-Subject-Token`
2. Call services with `X-Auth-Token` on the correct [port](../ports.md)

Default lab: `admin` / `secret`, project `demo`, domain `Default`.

## Cookbooks

- [Python (requests)](python-requests.md)
- [Python (openstacksdk)](python-openstacksdk.md)
- [Ansible](ansible.md)
- [Terraform](terraform.md)
- [Pulumi](pulumi.md)
- [CLI](openstack-cli.md)
- [Troubleshooting](troubleshooting-clients.md)

## API coverage lab (Pulumi)

Full guide: [hypervisor-lab.md](../hypervisor-lab.md)

```bash
cd pulumi-tests
make up
make test-pulumi-smoke
make test-pulumi
open reports/pulumi-report.html
```

Probe scripts (simulator conformance helpers):

| Script | Purpose |
|---|---|
| `examples/python/openstack_smoke.py` | Multi-port GET smoke |
| `examples/python/openstack_surface_probe.py` | Pack operation probe (also used by Pulumi lab) |
