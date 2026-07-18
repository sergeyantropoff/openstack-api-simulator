**Language / Язык:** [English](operations.md) | [Русский](ru/operations.md)

# Operations

## Day-2 commands (Compose)

```bash
make up                 # start stack
make down               # stop stack
make restart
make logs
make db-migrate         # idempotent migrations
make seed               # minimal OpenStack seed
make seed-demo          # demo cloud (~1000 servers)
make smoke              # multi-service GET smoke
```

## Migrations

Ordered SQL under `app/db/migrations/` applies transactionally.
Re-running `make db-migrate` is safe. `/health/ready` stays unavailable until
migrations are applied. Helm runs the same migrate step as an initContainer.

## Reseed

```bash
make seed               # minimal
make seed-demo          # replaces state with demo cloud
```

Or:

```bash
docker compose exec simulator python -m app.openstack.seed_cli --profile demo
```

Reseed **truncates** OpenStack lab tables and reloads. External automation that
cached resource UUIDs must refresh.

## OpenStack pack series

Cold start (env):

```bash
OPENSTACK_SERIES=caracal docker compose up -d
```

Helm:

```bash
--set config.openstackSeries=yoga
```

Hot-swap (Web UI or API):

```bash
curl -X POST http://127.0.0.1:5000/ui/api/openstack/contracts/activate \
  -H 'Content-Type: application/json' \
  -d '{"series":"dalmatian"}'
```

Series: `yoga`, `antelope`, `caracal`, `dalmatian`. Coverage:
[api_coverage.md](api_coverage.md).

## Regenerating contract packs

```bash
PYTHONPATH=tools python3 tools/os_api_inventory/generate_packs.py
PYTHONPATH=tools python3 tools/os_api_inventory/coverage_report.py
```

## Request body schemas (console)

Write methods (`POST`/`PUT`/`PATCH`) expose full JSON Schema field lists in the
web console. Schemas live in `contracts/openstack/request_bodies/<service>.json`
and are merged onto pack operations at load time (shared across series).

```bash
make request-bodies-generate   # rebuild from in-repo api-ref catalog
make request-bodies-import     # overlay Tier-1 services from openstack-openapi
make request-bodies-coverage   # assert every write op has a schema
```

Tier-1 OpenAPI import covers nova, neutron, keystone, glance, cinder, octavia,
swift, and placement. Other services use the curated catalog generator.

## Backing up lab state

PostgreSQL is the system of record. Use `pg_dump` / volume snapshots.
Application containers are disposable when the database volume remains.

## Publishing to Docker Hub

```bash
docker login
make release
```

| Variable | Default | Meaning |
|---|---|---|
| `DOCKERHUB_USER` | `inecs` | Docker Hub namespace |
| `IMAGE_NAME` | `openstack-api-simulator` | Repository name |
| `VERSION` | from `pyproject.toml` | Image tag |

```bash
make release VERSION=0.2.0
make release-build   # local tags only
```

## Kubernetes day-2

See [kubernetes.md](kubernetes.md) for logs, reseed via `kubectl exec`, and
uninstall.

## Testing

| Location | What |
|---|---|
| `tests/unit/` | Offline unit tests (ASGI / FakeDatabase) |
| `tests/openstack/` | Pack contracts, registry, live surface / lifecycle |
| `tests/integration/` | Postgres-backed integration |
| `tests/compatibility/` | Surface probe + group smoke markers |
| `examples/python/openstack_smoke.py` | Host multi-port smoke (`make smoke` / `make test-compatibility`) |
| `examples/python/openstack_surface_probe.py` | Lifecycle probe every pack op × series |
| [`pulumi-tests/`](../pulumi-tests/README.md) | Pulumi Layer B + full HTTP matrix (yoga→dalmatian) |

```bash
make test                 # offline unit + contract (no Postgres)
make test-integration     # -m integration (Postgres)
make test-surface         # surface probe + tests/openstack against Compose
make test-compatibility   # seed minimal + openstack_smoke.py
make pulumi-tests         # full pulumi-tests suite (alias: make test-pulumi)
make test-pulumi-smoke    # fast collection GET + HEAD only
```

Details for the Pulumi lab: [hypervisor-lab.md](hypervisor-lab.md).
Reports: `pulumi-tests/reports/pulumi-report.html`, `pulumi-junit.xml`, `summary.json`.

### Latest lab results (2026-07-18)

| Suite | Result |
|---|---|
| `make test` | 243 passed (34 deselected) |
| `make test-integration` | 33 passed |
| Surface probe (yoga→dalmatian) | 1464 / 1530 / 1649 / 1871 ops — **0 fail** |
| `make pulumi-tests` (full matrix) | HTTP **6514 / 6514**, `http_critical=0`, pulumi **4 / 4** series |
| Compatibility smoke | OK (auto Keystone `:5000` or local `:15000`) |

Regenerate the HTML report anytime with `make -C pulumi-tests report` after a suite run.

## Upgrades

1. Pull / build new image tag.
2. Apply migrations (automatic on start / Helm initContainer).
3. Optionally reseed if the seed schema changed.
4. Re-run `make smoke` or lifecycle probes.
