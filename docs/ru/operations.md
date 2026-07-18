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

## CI лаборатории покрытия API (pulumi-tests)

Pulumi прогоняет каждую pack-операцию по сериям — см.
[hypervisor-lab.md](hypervisor-lab.md).

```bash
make test-pulumi-smoke    # from repo root
make test-pulumi
```

Отчёты: `pulumi-tests/reports/pulumi-report.html` и `pulumi-junit.xml`.

## Обновления

1. Pull / build нового тега образа.
2. Примените миграции (автоматически при старте / Helm initContainer).
3. Опционально reseed, если изменилась seed-схема.
4. Повторите `make smoke` или lifecycle probes.
