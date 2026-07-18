**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Pulumi OpenStack tests (`pulumi-tests`)

**100% coverage = HTTP contract matrix** (every series-pack operation + synthetic
`HEAD` on each GET path), not the number of `pulumi_openstack` resources.

Layer A (gate): pack ops × yoga→dalmatian on **real service ports**
([docs/ports.md](../docs/ports.md)), microversions when the pack declares them,
non-empty success bodies for entity/collection envelopes, `probed == declared + HEAD`,
`critical=0`.

Layer B (smoke): `pulumi_openstack` lifecycle — maximises provider surface; does
**not** define 100%.

## Quick start

```bash
# from repo root
make pulumi-tests

# or
cd pulumi-tests
make up && make build
make test-pulumi-smoke   # fast: collection GET + HEAD
make test-pulumi         # full Layer A matrix × all series
open reports/pulumi-report.html
```

## Smoke vs full suite

| Target | Mode | What is exercised |
|---|---|---|
| `make test-pulumi-smoke` | Smoke (`TEST_SMOKE=1`) | Layer B + **collection GET + HEAD** nonempty checks (fast) |
| `make pulumi-tests` / `make test-pulumi` | Full matrix | Layer B + **every pack op × GET/POST/PUT/PATCH/DELETE** + **synthetic HEAD per GET**, completeness (`total == declared + HEAD`), nonempty bodies on succeeded responses (DELETE/204/HEAD may be empty) |

Pack sizes (ops, without HEAD): yoga ~1060 → antelope ~1108 → caracal ~1196 → **dalmatian ~1357**.

## What runs (per series: yoga → dalmatian)

1. Activate OpenStack series pack
2. **`pulumi up`** `programs/os_coverage` (Layer B — provider smoke)
3. Assert stack exports are non-empty (Layer B)
4. HTTP contract matrix on **catalog ports** (Keystone token → Nova `:8774`, Neutron `:9696`, …)
5. Assert `probed == declared + HEAD`, `critical=0`, nonempty JSON on success bodies
6. `pulumi destroy`
7. Write `pulumi-report.html` + `pulumi-junit.xml` + verb histogram (incl. HEAD)

## Reports

| File | Contents |
|---|---|
| `reports/pulumi-report.html` | HTML summary (expected vs actual + method breakdown incl. HEAD) |
| `reports/pulumi-junit.xml` | JUnit |
| `reports/series-<name>.json` | Per-series pulumi + HTTP details |
| `reports/summary.json` | Aggregates (`http_total` / `http_expected`, `http_critical`) |

## Latest results (2026-07-18)

Full matrix (`make test-pulumi` / `make pulumi-tests`):

| Metric | Value |
|---|---|
| Series | yoga → dalmatian (4) |
| `pulumi_ok` | 4 / 4 |
| HTTP probed | **6514 / 6514** (`declared` 4721 + synthetic `HEAD` 1793) |
| `http_critical` | **0** |
| Per series | yoga 1464 · antelope 1530 · caracal 1649 · dalmatian 1871 |

Open `reports/pulumi-report.html` after a run. Pytest / smoke locations for the
whole repo: [docs/operations.md — Testing](../docs/operations.md#testing).

## Approximate (not blockers)

Nova create may skip a long `BUILD` window; many Nova actions only flip server
status; Placement mutations and Octavia listeners/pools are largely schema /
`os_api_objects`; Neutron `router:external` is derived from the shared `public`
network name.
