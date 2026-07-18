**Language / Язык:** [English](architecture.md) | [Русский](ru/architecture.md)

# Architecture

## Components

```
┌─────────────┐     ┌──────────────────┐     ┌────────────┐
│  Clients    │────▶│  api-gateway     │────▶│ simulator  │
│  SDK / CLI  │     │  nginx multi-port│     │ FastAPI    │
│  Web UI     │     │  :5000,:8774,…   │     │ :8080      │
└─────────────┘     └──────────────────┘     └─────┬──────┘
                                                    │
                                              ┌─────▼──────┐
                                              │ PostgreSQL │
                                              └────────────┘
```

| Piece | Responsibility |
|---|---|
| **api-gateway** | Publish OpenStack default ports; set `X-OpenStack-Service` / `X-Forwarded-Port` |
| **ServiceDispatchMiddleware** | Rewrite to `/_os/<service>/…` |
| **Specialized routers** | Stateful Keystone, Nova, Neutron, Glance, Cinder, Heat, Swift, Ironic, Octavia, Placement |
| **Schema engine** | Surface-complete ops from `contracts/openstack/<series>/` |
| **PostgreSQL** | Identity, IaaS tables, `os_api_objects` generic store |

## Request lifecycle

1. Client hits e.g. `http://host:8774/v2.1/servers`.
2. Gateway injects service headers.
3. Dispatch mounts the request under `/_os/nova/…`.
4. Specialized Nova handler **or** schema pack operation runs.
5. Reads/writes go to PostgreSQL (typed tables or `os_api_objects`).

## Contract packs

- Generated inventory → `contracts/openstack/{yoga,antelope,caracal,dalmatian}/`
- Hot-swap via Web UI / `/ui/api/openstack/contracts/activate`
- Coverage report: [api_coverage.md](api_coverage.md)

## Seed profiles

| Profile | Contents |
|---|---|
| `minimal` | Small Keystone + few IaaS resources |
| `demo` | ~1000 servers, multi-project topology, nested collections |

Details: [seed-profiles.md](seed-profiles.md).

## Deployment model

| Mode | Gateway | DB |
|---|---|---|
| Compose | nginx container | bundled Postgres |
| Helm | nginx Deployment + multi-port Service | bundled StatefulSet or external |
| Ingress | TLS terminates at Ingress → gateway:5000 | — |

See [kubernetes.md](kubernetes.md).
