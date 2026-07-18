**Language / Язык:** [English](../configuration.md) | [Русский](configuration.md)

# Конфигурация

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Адрес привязки |
| `APP_PORT` | `8080` | Внутренний порт FastAPI (не публичный порт Keystone) |
| `DATABASE_URL` | (compose/helm) | PostgreSQL DSN |
| `TICKET_SIGNING_KEY` | lab secret | Материал подписи токенов (ротируйте в общих лабораториях) |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `OPENSTACK_SERIES` | `dalmatian` | Серия contract-пакета при холодном старте |
| `REQUEST_ID_HEADER` | `X-Request-ID` | Заголовок корреляции запросов |
| `SEED_PROFILE` | `minimal` | Для `seed_cli` / Helm seed Job (`minimal` / `demo`) |

## Compose

| Файл | Роль |
|---|---|
| `docker-compose.yml` | Dev-стек (build + bind mounts) |
| `docker-compose.release.yml` | Опубликованный Hub-образ |
| `.env` / `.env.example` | Локальные переопределения |

Сервисы:

- **simulator** — FastAPI на внутреннем `8080`
- **api-gateway** — nginx, публикующий реальные порты API OpenStack 1:1 ([ports.md](ports.md))
- **postgres** — `postgres:17.5-bookworm` на хосте `127.0.0.1:5433`

## Helm

См. [kubernetes.md](kubernetes.md) и
[`helm/openstack-api-simulator/values.yaml`](../../helm/openstack-api-simulator/values.yaml).

Важные параметры:

| Value | Назначение |
|---|---|
| `gateway.enabled` | Multi-port nginx (по умолчанию `true`) |
| `config.openstackSeries` | Env `OPENSTACK_SERIES` |
| `seed.profile` | `minimal` / `demo` |
| `postgresql.enabled` | Встроенная БД |
| `secret.ticketSigningKey` | Нужно ротировать для общих кластеров |

## Contract-пакеты

Расположение: `contracts/openstack/<series>/`.

В каждой серии — per-service пакеты `api.json`, потребляемые schema-движком.
Специализированные роутеры (Keystone, Nova, Neutron, …) остаются stateful для happy-path'ов.

## Переопределения Web UI

API catalog drawer: карточка серии → microversion в карточке → **Apply as runtime**.
