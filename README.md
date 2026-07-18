**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# openstack-api-simulator

Stateful laboratory simulator for OpenStack APIs: Keystone auth, a multi-port
gateway on OpenStack default ports, specialized
Nova/Neutron/Glance/Cinder/Heat/Swift/Ironic/Octavia handlers, and
schema-complete coverage for the remaining catalog services (Yoga → Dalmatian).

![Web console](docs/images/web-ui/console-main.png)

## Quick start (Compose)

### Published image (Docker Hub)

Clone this repository (api-gateway nginx config and lab TLS files are bind-mounted
from `./docker/`), then pull and run the published runtime image — no local app
build:

```bash
git clone https://github.com/inecs/openstack-api-simulator.git
cd openstack-api-simulator

docker compose -f docker-compose.release.yml up -d --wait
# or: make release-up

curl -sf http://127.0.0.1:5000/health/ready

# Optional full synthetic cloud (~1000 servers)
make release-seed PROFILE=demo
```

Image: [`inecs/openstack-api-simulator`](https://hub.docker.com/r/inecs/openstack-api-simulator)
(publish with `make release` when ready).

### Development checkout

```bash
cp .env.example .env
docker compose up -d --build --wait

# Optional full synthetic cloud (~1000 servers)
make seed-demo

# Full multi-service smoke
make smoke
```

- Console: [http://localhost:5000/](http://localhost:5000/)
- OpenAPI: [http://localhost:5000/docs](http://localhost:5000/docs)

More detail: [Getting started](docs/getting-started.md).

### Helm (Kubernetes + Ingress + Let's Encrypt)

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  -f ./helm/openstack-api-simulator/values-ingress-example.yaml \
  --set certManager.email=you@example.com \
  --set ingress.hosts[0].host=os-sim.example.com \
  --set ingress.tls[0].hosts[0]=os-sim.example.com \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)" \
  --set postgresql.auth.password="$(openssl rand -hex 16)"
```

Details: **[Kubernetes / Helm](docs/kubernetes.md)** · chart README:
[`helm/openstack-api-simulator`](helm/openstack-api-simulator).

Minimal ClusterIP + port-forward:

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)" \
  --set seed.enabled=true --set seed.profile=minimal

kubectl -n openstack-sim port-forward \
  svc/os-sim-openstack-api-simulator-gateway \
  5000:5000 8774:8774 9696:9696 9292:9292 8776:8776
```

### Credentials (seeded)

**Minimal seed** (default on startup):

| User | Password | Project | Role |
|---|---|---|---|
| `admin` | `secret` | `admin` / `demo` | admin |
| `demo` | `secret` | `demo` | member |

**Demo cloud** (Data drawer → *Load demo cloud* / `make seed-demo`): ~1000 servers,
16 hypervisors, 3 AZs, 5 projects, networks/ports/FIPs, 600 volumes, LBs, stacks,
Ironic, Swift.

| User | Password | Typical projects |
|---|---|---|
| `admin` | `secret` | all projects |
| `ops` | `secret` | production, staging |
| `developer` | `secret` | development, staging |
| `demo` / `auditor` | `secret` | demo / production |

Domain: `Default`.

### Auth example

```bash
curl -i -X POST http://localhost:5000/v3/auth/tokens \
  -H 'Content-Type: application/json' \
  -d '{
    "auth": {
      "identity": {
        "methods": ["password"],
        "password": {
          "user": {
            "name": "demo",
            "domain": {"name": "Default"},
            "password": "secret"
          }
        }
      },
      "scope": {
        "project": {"name": "demo", "domain": {"name": "Default"}}
      }
    }
  }'
# Use X-Subject-Token as X-Auth-Token.

curl -sH "X-Auth-Token: $TOKEN" -H "OpenStack-API-Version: compute 2.79" \
  http://localhost:8774/v2.1/servers/detail
curl -sH "X-Auth-Token: $TOKEN" http://localhost:9696/v2.0/routers
```

## Documentation

Documentation is bilingual. Use the **Language / Язык** switcher at the top of
each page, or open the Russian root [README.ru.md](README.ru.md). Index:
[docs/README.md](docs/README.md) · [docs/ru/README.md](docs/ru/README.md).

| Guide | Topic |
|---|---|
| [Getting started](docs/getting-started.md) | First lab session (Compose) |
| [Kubernetes / Helm](docs/kubernetes.md) | Cluster install, Ingress, cert-manager |
| [Configuration](docs/configuration.md) | Env vars, Compose, Helm knobs |
| [Authentication](docs/authentication.md) | Keystone tokens & seeded users |
| [Ports](docs/ports.md) | Real OpenStack API ports (1:1 host publish) |
| [API surface](docs/api-surface.md) | Specialized vs schema packs |
| [API versions](docs/api-versions.md) | Yoga → Dalmatian series |
| [API coverage](docs/api_coverage.md) | Generated operation counts |
| [Seed profiles](docs/seed-profiles.md) | `minimal` / `demo` |
| [Clients](docs/clients.md) | SDK / CLI |
| [Web UI](docs/web-ui.md) | Console drawers |
| [Operations](docs/operations.md) | Day-2, release, reseed |
| [Architecture](docs/architecture.md) | Components & request path |
| [Security](docs/security.md) | Lab threat model |
| [Observability](docs/observability.md) | Health & logs |
| [Troubleshooting](docs/troubleshooting.md) | Common failures |
| [FAQ](docs/faq.md) | Short Q&A |
| [Domains](docs/domains/README.md) | Per-service notes |
| [Examples](docs/examples/overview.md) | Client cookbooks |
| [Hypervisor-lab](docs/hypervisor-lab.md) | Pulumi API coverage (all ops × series) |

## API coverage lab (Pulumi)

Suite under [`pulumi-tests/`](pulumi-tests/) maximises **`pulumi_openstack`**,
then HTTP-probes pack ops with **non-empty** checks for **yoga → dalmatian**.

```bash
make pulumi-tests            # from repo root
# or:
cd pulumi-tests && make test-pulumi-smoke && make test-pulumi
open pulumi-tests/reports/pulumi-report.html
```

Details: **[docs/hypervisor-lab.md](docs/hypervisor-lab.md)**.

Full matrix of **real OpenStack default ports** published 1:1 (Keystone `:5000`,
Nova `:8774`, Neutron `:9696`, Glance `:9292`, Cinder `:8776`, …): see
[docs/ports.md](docs/ports.md).

Nginx sets `X-OpenStack-Service` / `X-Forwarded-Port`. The app rewrites to
`/_os/<service>/…` so `/v3` (Keystone vs Cinder) and `/v1` (Heat vs Swift) do not collide.

## Implemented API surface

Contract packs under `contracts/openstack/<series>/` drive **1300+ operations**
across **28 services** (Yoga → Dalmatian). The schema engine mounts every pack
operation; specialized routers keep stateful happy-paths.

| Tooling | Purpose |
|---|---|
| `PYTHONPATH=tools python3 tools/os_api_inventory/generate_packs.py` | Regenerate series packs |
| `python3 tools/os_api_inventory/coverage_report.py` | Write [docs/api_coverage.md](docs/api_coverage.md) |
| `python3 examples/python/openstack_smoke.py` | Multi-port GET smoke |
| `python3 examples/python/openstack_surface_probe.py` | Full lifecycle probe |

**WebUI:** Environment → OpenStack API pack — activate series and microversions.

This is a **lab surface-complete** simulator (API-ref shaped responses), not
bit-identical upstream OpenStack.

Console drawers, request parameters, and screenshots: **[Web UI](docs/web-ui.md)**.

## License

Apache-2.0 — see [LICENSE](LICENSE).
