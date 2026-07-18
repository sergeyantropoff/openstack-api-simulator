**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Контракты

## Пакеты OpenStack (канонические)

Surface-complete API-пакеты лежат в `contracts/openstack/<series>/`:

| Серия | Major (UI) | Manifest |
|---|---:|---|
| yoga | 6 | `contracts/openstack/yoga/manifest.json` |
| antelope | 7 | `contracts/openstack/antelope/manifest.json` |
| caracal | 8 | `contracts/openstack/caracal/manifest.json` |
| dalmatian | 9 | `contracts/openstack/dalmatian/manifest.json` |

Каждая серия покрывает **26 сервисов** с растущей поверхностью:

| Серия | Операции |
|---|---:|
| Yoga | 997 |
| Antelope | 1039 |
| Caracal | 1115 |
| Dalmatian | 1144 |

Дельты заданы в `tools/os_api_inventory/series_deltas.py`. Пакеты управляют:

- маршрутами schema-движка (`app/openstack/schema_engine.py`);
- каталогом WebUI / Environment drawer (`/ui/api/openstack/contracts`);
- отчётом о покрытии (`docs/api_coverage.md` · [русская версия](../docs/ru/api_coverage.md)).

Перегенерация:

```bash
python -m tools.os_api_inventory.generate_packs
python -m tools.os_api_inventory.coverage_report
```
