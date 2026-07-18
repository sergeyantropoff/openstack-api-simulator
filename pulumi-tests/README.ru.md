**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Тесты Pulumi OpenStack (`pulumi-tests`)

**100% покрытия = HTTP contract matrix** (каждая операция series-pack +
синтетический `HEAD` на каждый GET path), а не число ресурсов `pulumi_openstack`.

Layer A (гейт): pack ops × yoga→dalmatian на **реальных портах сервисов**
([docs/ports.md](../docs/ports.md) / [docs/ru/ports.md](../docs/ru/ports.md)),
microversions где pack их задаёт, nonempty тела успешных ответов,
`probed == declared + HEAD`, `critical=0`.

Layer B (smoke): lifecycle `pulumi_openstack` — расширяет provider surface; **не**
определяет 100%.

## Быстрый старт

```bash
# из корня репозитория
make pulumi-tests

# или
cd pulumi-tests
make up && make build
make test-pulumi-smoke   # быстро: collection GET + HEAD
make test-pulumi         # полная Layer A matrix × все серии
open reports/pulumi-report.html
```

## Smoke vs полный suite

| Цель | Режим | Что проверяется |
|---|---|---|
| `make test-pulumi-smoke` | Smoke (`TEST_SMOKE=1`) | Layer B + **collection GET + HEAD** с nonempty (быстро) |
| `make pulumi-tests` / `make test-pulumi` | Полная matrix | Layer B + **все ops пака × GET/POST/PUT/PATCH/DELETE** + **синтетический HEAD на каждый GET**, полнота (`total == declared + HEAD`), nonempty тел (DELETE/204/HEAD могут быть пустыми) |

Размеры паков (ops без HEAD): yoga ~1060 → antelope ~1108 → caracal ~1196 → **dalmatian ~1357**.

## Что выполняется (на каждую серию yoga → dalmatian)

1. Активация pack серии OpenStack
2. **`pulumi up`** `programs/os_coverage` (Layer B — provider smoke)
3. Проверка непустых export стека (Layer B)
4. HTTP contract matrix на **портах каталога** (токен Keystone → Nova `:8774`, Neutron `:9696`, …)
5. Assert `probed == declared + HEAD`, `critical=0`, nonempty JSON
6. `pulumi destroy`
7. Отчёты HTML/JUnit + histogram глаголов (включая HEAD)

## Отчёты

| Файл | Содержимое |
|---|---|
| `reports/pulumi-report.html` | HTML-сводка (expected vs actual + breakdown методов вкл. HEAD) |
| `reports/pulumi-junit.xml` | JUnit |
| `reports/series-<name>.json` | Детали pulumi + HTTP по серии |
| `reports/summary.json` | Агрегаты (`http_total` / `http_expected`, `http_critical`) |

## Approximate (не блокеры)

Nova create может пропускать длинное окно `BUILD`; многие Nova actions только
меняют status; Placement mutations и Octavia listeners/pools в основном schema /
`os_api_objects`; Neutron `router:external` выводится из shared сети `public`.
