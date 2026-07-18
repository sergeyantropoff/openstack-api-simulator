**Language / Язык:** [English](clients.md) | [Русский](ru/clients.md)

# Clients

## Connection matrix

| Client | Auth URL | Notes |
|---|---|---|
| curl | `http://127.0.0.1:5000/v3` | Use `X-Subject-Token` → `X-Auth-Token` |
| openstack CLI | `OS_AUTH_URL=…/v3` | See [authentication.md](authentication.md) |
| openstacksdk | same | Service catalog ports must match gateway |
| Terraform OpenStack provider | `auth_url` | Point at Keystone; catalog drives Nova/Neutron |
| Ansible `openstack.*` | clouds.yaml | Same credentials as CLI |

## Compose (local)

```bash
export OS_AUTH_URL=http://127.0.0.1:5000/v3
export OS_USERNAME=admin
export OS_PASSWORD=secret
export OS_PROJECT_NAME=demo
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_DOMAIN_NAME=Default
export OS_IDENTITY_API_VERSION=3
```

## Helm / Ingress

```bash
export OS_AUTH_URL=https://os-sim.example.com/v3
# Other services: either port-forward gateway ports or rely on catalog URLs
# that your Ingress/DNS map correctly.
```

For multi-port access without Ingress TCP, port-forward the gateway Service
(see [kubernetes.md](kubernetes.md)).

## Examples in-repo

| Path | Purpose |
|---|---|
| `examples/python/openstack_smoke.py` | Multi-port GET smoke |
| `examples/python/openstack_conformance.py` | Write-path sample |
| `examples/python/openstack_surface_probe.py` | Full pack lifecycle probe |

Cookbooks: [examples/](examples/).
