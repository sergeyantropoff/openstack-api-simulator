**Language / Язык:** [English](../web-ui.md) | [Русский](web-ui.md)

# Web UI

Консоль обслуживается с Keystone/UI порта (**5000** на gateway).

| URL | Назначение |
|---|---|
| `/` или `/console` | Интерактивная консоль |
| `/docs` | OpenAPI (simulator) |
| `/ui/api/…` | UI JSON APIs |

## Environment drawer

- **OpenStack API pack** — список серий, активация пакета, переопределения microversion
- Apply немедленно перемонтирует schema-маршруты

## Data drawer

- **Load demo cloud** — `POST /ui/api/demo/load` → `seed_openstack_demo`
- **Unload / minimal** — сброс к minimal seed

## Брендинг

OpenStack red `#ED1C24`, console wordmark. Темы следуют общему chrome консоли
(light/dark).

## Health

- `/health/live` — процесс работает
- `/health/ready` — миграции применены + БД доступна
