**Language / Язык:** [English](hypervisor-lab.md) | [Русский](ru/hypervisor-lab.md)

# Pulumi OpenStack coverage lab

Suite under [`pulumi-tests/`](../pulumi-tests/) that maximises
**`pulumi_openstack`**, then HTTP-probes pack operations with **non-empty**
response checks across **yoga → dalmatian**.

## Quick start

```bash
make pulumi-tests          # from repo root (full suite)
make test-pulumi-smoke     # fast collection mode
```

Or:

```bash
cd pulumi-tests
make up && make build
make test-pulumi
open reports/pulumi-report.html
```

## Flow (per series)

1. Activate series pack
2. Pulumi Automation API → `programs/os_coverage` (`pulumi_openstack` resources + data sources)
3. Assert every export is non-empty
4. HTTP probe remaining/all pack ops; require non-empty bodies on successful GET/POST
5. Destroy stack; emit HTML + JUnit

See [`pulumi-tests/README.md`](../pulumi-tests/README.md).
Broader pytest / smoke map: [operations.md — Testing](operations.md#testing).

## Latest results (2026-07-18)

Full suite (`make pulumi-tests`, `collections_only=false`):

| Series | HTTP ok / total | Pulumi |
|---|---:|---|
| yoga | 1464 / 1464 | ok |
| antelope | 1530 / 1530 | ok |
| caracal | 1649 / 1649 | ok |
| dalmatian | 1871 / 1871 | ok |
| **All** | **6514 / 6514** (`http_critical=0`) | **4 / 4** |

Artifacts: `pulumi-tests/reports/pulumi-report.html`, `summary.json`.
