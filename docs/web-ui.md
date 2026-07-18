**Language / Язык:** [English](web-ui.md) | [Русский](ru/web-ui.md)

# Web UI

Console is served from the Keystone/UI port (**5000** on the gateway).

| URL | Purpose |
|---|---|
| `/` or `/console` | Interactive console |
| `/docs` | OpenAPI (simulator) |
| `/ui/api/…` | UI JSON APIs |

## Environment drawer

- **OpenStack API pack** — list series, activate pack, set microversion overrides
- Apply remounts schema routes immediately

## Data drawer

- **Load demo cloud** — `POST /ui/api/demo/load` → `seed_openstack_demo`
- **Unload / minimal** — reset to minimal seed

## Branding

OpenStack red `#ED1C24`, console wordmark. Themes follow the shared console
chrome (light/dark).

## Health

- `/health/live` — process up
- `/health/ready` — migrations applied + DB reachable
