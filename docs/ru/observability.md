**Language / Язык:** [English](../observability.md) | [Русский](observability.md)

# Наблюдаемость

## Health endpoints

| Path | Значение |
|---|---|
| `/health/live` | Процесс работает |
| `/health/ready` | БД доступна + миграции применены |

Оба доступны на simulator и через gateway (на любом опубликованном порту).

## Request IDs

Заголовок `X-Request-ID` (настраивается через `REQUEST_ID_HEADER`) принимается и
эхом возвращается там, где применяется middleware.

## Логи

Compose:

```bash
make logs
docker compose logs -f simulator api-gateway
```

Helm:

```bash
kubectl logs -l app.kubernetes.io/component=simulator -f
kubectl logs -l app.kubernetes.io/component=gateway -f
```

## Доказательства совместимости / покрытия

- Покрытие пакетов: [api_coverage.md](api_coverage.md)
- Live lifecycle: `examples/python/openstack_surface_probe.py`
- pytest: `tests/openstack/` (включая real-DB conformance)
