**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Pulumi OpenStack tests (`pulumi-tests`)

Coverage lab that **maximises `pulumi_openstack`**, then probes remaining pack
operations over HTTP with **non-empty body checks** and **full method coverage**.

## Quick start

```bash
# from repo root
make pulumi-tests

# or
cd pulumi-tests
make up && make build
make test-pulumi-smoke   # fast: collection GET only
make test-pulumi         # full: all pack ops × all HTTP methods
open reports/pulumi-report.html
```

## Smoke vs full suite

| Target | Mode | What is exercised |
|---|---|---|
| `make test-pulumi-smoke` | Smoke (`TEST_SMOKE=1`) | `pulumi_openstack` + **collection GET** nonempty checks (fast) |
| `make pulumi-tests` / `make test-pulumi` | Full lifecycle | `pulumi_openstack` + **every pack operation × GET/POST/PUT/PATCH/DELETE**, completeness assert (`total == pack size`), nonempty bodies on succeeded responses (DELETE/204 may be empty) |

Pack sizes (ops): yoga ~1060 → antelope ~1108 → caracal ~1196 → **dalmatian ~1357**.

## What runs (per series: yoga → dalmatian)

1. Activate OpenStack series pack
2. **`pulumi up`** `programs/os_coverage` via Automation API — creates/looks up
   resources with `pulumi_openstack` (identity, images, compute, networking,
   blockstorage, objectstorage, dns, orchestration)
3. Assert **every stack export is non-empty**
4. HTTP-probe pack operations (smoke: collection GET; full: all methods lifecycle)
5. Assert coverage completeness + nonempty JSON on successful body responses
6. `pulumi destroy`
7. Write `pulumi-report.html` + `pulumi-junit.xml`

## Reports

| File | Contents |
|---|---|
| `reports/pulumi-report.html` | HTML summary (expected vs actual + method breakdown) |
| `reports/pulumi-junit.xml` | JUnit |
| `reports/series-<name>.json` | Per-series pulumi + HTTP details |
| `reports/summary.json` | Aggregates |
