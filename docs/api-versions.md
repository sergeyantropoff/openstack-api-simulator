**Language / Язык:** [English](api-versions.md) | [Русский](ru/api-versions.md)

# API versions (series packs)

The simulator ships **four** OpenStack release series as contract packs:

| Series | OpenStack release family | Cold-start env |
|---|---|---|
| `yoga` | Yoga | `OPENSTACK_SERIES=yoga` |
| `antelope` | Antelope | `OPENSTACK_SERIES=antelope` |
| `caracal` | Caracal | `OPENSTACK_SERIES=caracal` |
| `dalmatian` | Dalmatian (default) | `OPENSTACK_SERIES=dalmatian` |

## Cold start

Compose / process:

```bash
OPENSTACK_SERIES=caracal docker compose up -d
```

Helm:

```bash
--set config.openstackSeries=yoga
```

## Hot-swap

```bash
curl -X POST http://127.0.0.1:5000/ui/api/openstack/contracts/activate \
  -H 'Content-Type: application/json' \
  -d '{"series":"dalmatian"}'
```

Or Web UI → Environment → OpenStack API pack → Activate.

Hot-swap remounts schema routes (`remount_schema_services`) without rebuilding
the image.

## Pack layout

```
contracts/openstack/<series>/
  manifest.json
  keystone/api.json
  nova/api.json
  neutron/api.json
  …
```

Regenerate:

```bash
PYTHONPATH=tools python3 tools/os_api_inventory/generate_packs.py
```
