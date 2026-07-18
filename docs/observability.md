**Language / Язык:** [English](observability.md) | [Русский](ru/observability.md)

# Observability

## Health endpoints

| Path | Meaning |
|---|---|
| `/health/live` | Process is running |
| `/health/ready` | DB reachable + migrations applied |

Both are exposed on the simulator and via the gateway (any published port).

## Request IDs

Header `X-Request-ID` (configurable via `REQUEST_ID_HEADER`) is accepted and
echoed where middleware applies.

## Logs

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

## Compatibility / coverage evidence

- Pack coverage: [api_coverage.md](api_coverage.md)
- Live lifecycle: `examples/python/openstack_surface_probe.py`
- pytest: `tests/openstack/` (includes real-DB conformance)
