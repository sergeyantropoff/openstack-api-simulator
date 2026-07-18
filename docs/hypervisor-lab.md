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
