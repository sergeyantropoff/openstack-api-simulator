**Language / Язык:** [English](getting-started.md) | [Русский](ru/getting-started.md)

# Getting started

End-to-end first lab session with Docker Compose. For Kubernetes see
[kubernetes.md](kubernetes.md).

## Prerequisites

- Docker / Docker Compose
- Python 3.13+ (optional, for host-side smoke scripts)
- `curl` or `openstack` CLI / `openstacksdk`

## Choose a path

| Path | When |
|---|---|
| **1a. Published image** | Running lab from Hub image (`docker-compose.release.yml`; needs a repo checkout for gateway/TLS mounts) |
| **1b. Development checkout** | You will change code / packs |
| **Helm** | Cluster install — [kubernetes.md](kubernetes.md) |

## 1a. Published image (Docker Hub)

Requires a **git checkout** of this repo: Compose bind-mounts
`./docker/gateway` and `./docker/tls` into the nginx gateway. The simulator
container itself comes from Docker Hub (no local app build).

```bash
git clone https://github.com/inecs/openstack-api-simulator.git
cd openstack-api-simulator
docker compose -f docker-compose.release.yml up -d --wait
# or: make release-up
```

Image: [`inecs/openstack-api-simulator`](https://hub.docker.com/r/inecs/openstack-api-simulator).
Override tag with `IMAGE_TAG=0.1.0` if needed.

## 1b. Development checkout

```bash
cp .env.example .env
docker compose up -d --build --wait
```

## 2. Wait until ready

```bash
curl -sf http://127.0.0.1:5000/health/ready
```

## 3. Seed a profile

Minimal seed runs on first start. Optional full synthetic cloud:

```bash
make seed-demo
# or
docker compose exec simulator python -m app.openstack.seed_cli --profile demo
```

Profiles: [seed-profiles.md](seed-profiles.md).

## 4. Authenticate (Keystone)

```bash
export OS_AUTH_URL=http://127.0.0.1:5000/v3
TOKEN=$(curl -si -X POST "$OS_AUTH_URL/auth/tokens" \
  -H 'Content-Type: application/json' \
  -d '{
    "auth": {
      "identity": {
        "methods": ["password"],
        "password": {
          "user": {
            "name": "admin",
            "domain": {"name": "Default"},
            "password": "secret"
          }
        }
      },
      "scope": {
        "project": {"name": "demo", "domain": {"name": "Default"}}
      }
    }
  }' | awk -F': ' 'tolower($1)=="x-subject-token"{print $2}' | tr -d '\r')
echo "token=$TOKEN"
```

## 5. Call Nova / Neutron

```bash
curl -sH "X-Auth-Token: $TOKEN" http://127.0.0.1:8774/v2.1/servers/detail | head -c 400
curl -sH "X-Auth-Token: $TOKEN" http://127.0.0.1:9696/v2.0/networks
```

## 6. Open the Web UI

[http://localhost:5000/](http://localhost:5000/) — console, Environment drawer
(OpenStack pack series + microversions), Data drawer (load/unload demo cloud).

## 7. Smoke / conformance

```bash
make smoke
python3 examples/python/openstack_smoke.py
python3 examples/python/openstack_conformance.py
```

## You're done when…

- `/health/ready` returns 200
- Keystone issues `X-Subject-Token`
- Nova/Neutron lists return seeded resources
- (optional) demo cloud shows ~1000 servers

## Next steps

- [Ports](ports.md) — full service port matrix
- [API coverage](api_coverage.md) — pack operations by series
- [Clients](clients.md) — openstacksdk / CLI
- [Kubernetes / Helm](kubernetes.md)
- [Hypervisor-lab](hypervisor-lab.md) — Pulumi API coverage (all ops × series)
- [Operations](operations.md)
