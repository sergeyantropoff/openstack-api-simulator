**Language / Язык:** [English](configuration.md) | [Русский](ru/configuration.md)

# Configuration

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8080` | Internal FastAPI port (not the public Keystone port) |
| `DATABASE_URL` | (compose/helm) | PostgreSQL DSN |
| `TICKET_SIGNING_KEY` | lab secret | Token/signing material (rotate in shared labs) |
| `LOG_LEVEL` | `INFO` | Logging |
| `OPENSTACK_SERIES` | `dalmatian` | Contract pack series at cold start |
| `REQUEST_ID_HEADER` | `X-Request-ID` | Request correlation header |
| `SEED_PROFILE` | `minimal` | Used by `seed_cli` / Helm seed Job (`minimal` / `demo`) |

## Compose

| File | Role |
|---|---|
| `docker-compose.yml` | Dev stack (build + bind mounts) |
| `docker-compose.release.yml` | Published Hub image |
| `.env` / `.env.example` | Local overrides |

Services:

- **simulator** — FastAPI on internal `8080`
- **api-gateway** — nginx publishing real OpenStack API ports 1:1 ([ports.md](ports.md))
- **postgres** — `postgres:17.5-bookworm` on host `127.0.0.1:5433`

## Helm

See [kubernetes.md](kubernetes.md) and
[`helm/openstack-api-simulator/values.yaml`](../helm/openstack-api-simulator/values.yaml).

Important knobs:

| Value | Purpose |
|---|---|
| `gateway.enabled` | Multi-port nginx (default `true`) |
| `config.openstackSeries` | Pack series env `OPENSTACK_SERIES` |
| `seed.profile` | `minimal` / `demo` |
| `postgresql.enabled` | Bundled DB |
| `secret.ticketSigningKey` | Must be rotated for shared clusters |

## Contract packs

Location: `contracts/openstack/<series>/`.

Each series has per-service `api.json` packs consumed by the schema engine.
Specialized routers (Keystone, Nova, Neutron, …) remain stateful for happy-paths.

## Web UI overrides

Environment drawer → **OpenStack API pack**:

- Activate series (hot remount)
- Per-service microversion override
