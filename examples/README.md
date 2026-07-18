**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Runnable OpenStack examples

Companion code for [docs/clients.md](../docs/clients.md) and
[docs/examples/overview.md](../docs/examples/overview.md).

This repo is an **OpenStack** API lab (not VMware). Use `openstack_*` Terraform
resources / `pulumi_openstack` — not `vsphere_virtual_machine`.

## Prerequisites

```bash
make up
make seed-demo   # networks, images (cirros), flavors, …
```

Default credentials: `admin` / `secret`, project `demo`, domain `Default`.  
Auth URL: `http://127.0.0.1:5000/v3`.

For local cookbooks, disable HTTP proxies (IDE sandboxes often inject one and
break multi-port Keystone/Glance/Nova discovery):

```bash
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY='*'
```

## Full stack (Python + Ansible + Terraform + Pulumi)

```bash
bash examples/run_iac_stack.sh
```

| Step | Path | What it does |
|---|---|---|
| Python | `python/openstacksdk_cookbook.py` | net/subnet + server + volume via openstacksdk |
| Ansible | `ansible/playbook.yml` | Keystone token + Nova/Neutron/Glance via `uri` |
| Terraform | `terraform/main.tf` | `openstack_compute_instance_v2` + volume attach |
| Pulumi | `pulumi/` | `pulumi_openstack` Instance + Network/Subnet |

## Other probes

| Path | Purpose |
|---|---|
| `python/openstack_smoke.py` | Multi-port GET smoke |
| `python/openstack_conformance.py` | Write-path + UI contracts |
| `python/openstack_surface_probe.py` | Full pack lifecycle probe |
