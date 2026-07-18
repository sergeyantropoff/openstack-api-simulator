**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Contracts

## OpenStack packs (canonical)

Surface-complete API packs live under `contracts/openstack/<series>/`:

| Series | Major (UI) | Manifest |
|---|---:|---|
| yoga | 6 | `contracts/openstack/yoga/manifest.json` |
| antelope | 7 | `contracts/openstack/antelope/manifest.json` |
| caracal | 8 | `contracts/openstack/caracal/manifest.json` |
| dalmatian | 9 | `contracts/openstack/dalmatian/manifest.json` |

Each series covers **26 services** with growing surfaces:

| Series | Operations |
|---|---:|
| Yoga | 997 |
| Antelope | 1039 |
| Caracal | 1115 |
| Dalmatian | 1144 |

Deltas are defined in `tools/os_api_inventory/series_deltas.py`. Packs drive:

- schema engine routes (`app/openstack/schema_engine.py`);
- WebUI catalog / Environment drawer (`/ui/api/openstack/contracts`);
- coverage report (`docs/api_coverage.md`).

Regenerate:

```bash
python -m tools.os_api_inventory.generate_packs
python -m tools.os_api_inventory.coverage_report
```
