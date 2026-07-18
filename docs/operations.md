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

## API coverage lab CI (pulumi-tests)

Pulumi probes every pack operation across series — see
[hypervisor-lab.md](hypervisor-lab.md).

```bash
make test-pulumi-smoke    # from repo root
make test-pulumi
```

Reports: `pulumi-tests/reports/pulumi-report.html` and `pulumi-junit.xml`.

## Upgrades

1. Pull / build new image tag.
2. Apply migrations (automatic on start / Helm initContainer).
3. Optionally reseed if the seed schema changed.
4. Re-run `make smoke` or lifecycle probes.
