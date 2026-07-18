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
