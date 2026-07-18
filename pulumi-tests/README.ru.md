**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Тесты Pulumi OpenStack (`pulumi-tests`)

Лаборатория покрытия: **максимально `pulumi_openstack`**, затем HTTP-probe
остальных pack-операций с проверкой **непустых тел** и **полным покрытием методов**.

## Быстрый старт

```bash
# из корня репозитория
make pulumi-tests

# или
cd pulumi-tests
make up && make build
make test-pulumi-smoke   # быстро: только collection GET
make test-pulumi         # полный: все ручки пака × все HTTP-методы
open reports/pulumi-report.html
```

## Smoke vs полный suite

| Цель | Режим | Что проверяется |
|---|---|---|
| `make test-pulumi-smoke` | Smoke (`TEST_SMOKE=1`) | `pulumi_openstack` + **collection GET** с nonempty (быстро) |
| `make pulumi-tests` / `make test-pulumi` | Полный lifecycle | `pulumi_openstack` + **все операции пака × GET/POST/PUT/PATCH/DELETE**, assert полноты (`total == размер пака`), nonempty тел успешных ответов (DELETE/204 могут быть пустыми) |

Размеры паков (ops): yoga ~1060 → antelope ~1108 → caracal ~1196 → **dalmatian ~1357**.

## Что выполняется (на каждую серию yoga → dalmatian)

1. Активация pack серии OpenStack
2. **`pulumi up`** программы `programs/os_coverage` через Automation API —
   ресурсы через `pulumi_openstack` (identity, images, compute, networking,
   blockstorage, objectstorage, dns, orchestration)
3. Проверка: **каждый export стека непустой**
4. HTTP-probe pack-операций (smoke: collection GET; полный: lifecycle всех методов)
5. Assert полноты покрытия + nonempty JSON у успешных ответов с телом
6. `pulumi destroy`
7. Отчёты `pulumi-report.html` + `pulumi-junit.xml`

## Отчёты

| Файл | Содержимое |
|---|---|
| `reports/pulumi-report.html` | HTML-сводка (expected vs actual + breakdown методов) |
| `reports/pulumi-junit.xml` | JUnit |
| `reports/series-<name>.json` | Детали pulumi + HTTP по серии |
| `reports/summary.json` | Агрегаты |
