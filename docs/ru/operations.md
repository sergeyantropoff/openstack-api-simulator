**Language / Язык:** [English](../operations.md) | [Русский](operations.md)

# Эксплуатация

## Day-2 команды (Compose)

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

## Миграции

Упорядоченный SQL в `app/db/migrations/` применяется транзакционно.
Повторный запуск `make db-migrate` безопасен. `/health/ready` остаётся недоступным,
пока миграции не применены. Helm выполняет тот же migrate-шаг как initContainer.

## Reseed

```bash
make seed               # minimal
make seed-demo          # replaces state with demo cloud
```

Или:

```bash
docker compose exec simulator python -m app.openstack.seed_cli --profile demo
```

Reseed **очищает** лабораторные таблицы OpenStack и перезагружает данные. Внешняя
автоматизация с закэшированными UUID ресурсов должна обновить их.

## OpenStack pack series

Cold start (env):

```bash
OPENSTACK_SERIES=caracal docker compose up -d
```

Helm:

```bash
--set config.openstackSeries=yoga
```

Hot-swap (Web UI или API):

```bash
curl -X POST http://127.0.0.1:5000/ui/api/openstack/contracts/activate \
  -H 'Content-Type: application/json' \
  -d '{"series":"dalmatian"}'
```

Серии: `yoga`, `antelope`, `caracal`, `dalmatian`. Покрытие:
[api_coverage.md](api_coverage.md).

## Перегенерация contract-пакетов

```bash
PYTHONPATH=tools python3 tools/os_api_inventory/generate_packs.py
PYTHONPATH=tools python3 tools/os_api_inventory/coverage_report.py
```

## Схемы Request body (консоль)

Для `POST`/`PUT`/`PATCH` консоль показывает полные JSON Schema поля.
Схемы лежат в `contracts/openstack/request_bodies/<service>.json` и
подмешиваются к операциям пака при загрузке (общие для всех серий).

```bash
make request-bodies-generate   # пересобрать из api-ref каталога
make request-bodies-import     # наложить Tier-1 из openstack-openapi
make request-bodies-coverage   # проверить, что у всех write-op есть схема
```

Tier-1: nova, neutron, keystone, glance, cinder, octavia, swift, placement.
Остальные сервисы — курируемый генератор каталога.

## Резервное копирование состояния лаборатории

PostgreSQL — источник истины. Используйте `pg_dump` / снимки volume.
Контейнеры приложения одноразовые, если volume БД сохранён.

## Публикация на Docker Hub

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

См. [kubernetes.md](kubernetes.md) для логов, reseed через `kubectl exec` и
удаления.

## Тестирование

| Где | Что |
|---|---|
| `tests/unit/` | Офлайн unit (ASGI / FakeDatabase) |
| `tests/openstack/` | Pack-контракты, registry, live surface / lifecycle |
| `tests/integration/` | Интеграция с PostgreSQL |
| `tests/compatibility/` | Surface probe и group smoke |
| `examples/python/openstack_smoke.py` | Host multi-port smoke (`make smoke` / `make test-compatibility`) |
| `examples/python/openstack_surface_probe.py` | Lifecycle-probe каждой pack-операции × серии |
| [`pulumi-tests/`](../../pulumi-tests/README.ru.md) | Pulumi Layer B + полная HTTP-матрица (yoga→dalmatian) |

```bash
make test                 # офлайн unit + contract (без Postgres)
make test-integration     # -m integration (Postgres)
make test-surface         # surface probe + tests/openstack против Compose
make test-compatibility   # seed minimal + openstack_smoke.py
make pulumi-tests         # полный сьют pulumi-tests (alias: make test-pulumi)
make test-pulumi-smoke    # быстрый режим: collection GET + HEAD
```

Подробнее о Pulumi-лаборатории: [hypervisor-lab.md](hypervisor-lab.md).
Отчёты: `pulumi-tests/reports/pulumi-report.html`, `pulumi-junit.xml`, `summary.json`.

### Последние результаты лаборатории (2026-07-18)

| Сьют | Результат |
|---|---|
| `make test` | 243 passed (34 deselected) |
| `make test-integration` | 33 passed |
| Surface probe (yoga→dalmatian) | 1464 / 1530 / 1649 / 1871 ops — **0 fail** |
| `make pulumi-tests` (полная matrix) | HTTP **6514 / 6514**, `http_critical=0`, pulumi **4 / 4** серии |
| Compatibility smoke | OK (авто Keystone `:5000` или локальный `:15000`) |

Пересобрать HTML-отчёт: `make -C pulumi-tests report` после прогона.

## Обновления

1. Pull / build нового тега образа.
2. Примените миграции (автоматически при старте / Helm initContainer).
3. Опционально reseed, если изменилась seed-схема.
4. Повторите `make smoke` или lifecycle probes.
