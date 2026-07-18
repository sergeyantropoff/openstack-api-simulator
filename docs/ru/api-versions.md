**Language / Язык:** [English](../api-versions.md) | [Русский](api-versions.md)

# Версии API (series packs)

Симулятор поставляет **четыре** серии релизов OpenStack как contract-пакеты:

| Series | OpenStack release family | Cold-start env |
|---|---|---|
| `yoga` | Yoga | `OPENSTACK_SERIES=yoga` |
| `antelope` | Antelope | `OPENSTACK_SERIES=antelope` |
| `caracal` | Caracal | `OPENSTACK_SERIES=caracal` |
| `dalmatian` | Dalmatian (default) | `OPENSTACK_SERIES=dalmatian` |

## Cold start

Compose / процесс:

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

Или Web UI → API catalog → выбрать серию → **Apply as runtime**.

Hot-swap перемонтирует schema-маршруты (`remount_schema_services`) без пересборки
образа.

## Структура пакета

```
contracts/openstack/<series>/
  manifest.json
  keystone/api.json
  nova/api.json
  neutron/api.json
  …
```

Перегенерация:

```bash
PYTHONPATH=tools python3 tools/os_api_inventory/generate_packs.py
```
