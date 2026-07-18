**Language / Язык:** [English](../hypervisor-lab.md) | [Русский](hypervisor-lab.md)

# Лаборатория покрытия Pulumi OpenStack

Сьют в [`pulumi-tests/`](../../pulumi-tests/): максимально **`pulumi_openstack`**,
затем HTTP-probe pack-операций с проверкой **непустых** ответов для серий
**yoga → dalmatian**.

## Быстрый старт

```bash
make pulumi-tests          # из корня (полный сьют)
make test-pulumi-smoke     # быстрый режим
```

Или:

```bash
cd pulumi-tests
make up && make build
make test-pulumi
open reports/pulumi-report.html
```

## Ход (на серию)

1. Активация pack серии
2. Pulumi Automation API → `programs/os_coverage` (`pulumi_openstack`)
3. Каждый export стека должен быть непустым
4. HTTP-probe pack-операций; непустые тела на успешных GET/POST
5. Destroy; HTML + JUnit

См. [`pulumi-tests/README.ru.md`](../../pulumi-tests/README.ru.md).
Карта pytest / smoke: [operations.md — Тестирование](operations.md#тестирование).

## Последние результаты (2026-07-18)

Полный сьют (`make pulumi-tests`, `collections_only=false`):

| Серия | HTTP ok / total | Pulumi |
|---|---:|---|
| yoga | 1464 / 1464 | ok |
| antelope | 1530 / 1530 | ok |
| caracal | 1649 / 1649 | ok |
| dalmatian | 1871 / 1871 | ok |
| **Все** | **6514 / 6514** (`http_critical=0`) | **4 / 4** |

Артефакты: `pulumi-tests/reports/pulumi-report.html`, `summary.json`.
