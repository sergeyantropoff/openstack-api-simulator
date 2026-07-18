**Language / Язык:** [English](../../domains/schema-services.md) | [Русский](schema-services.md)

# Schema-backed сервисы

Эти проекты в основном обслуживаются contract-пакетами + `os_api_objects`
(demo seed вставляет несколько строк на тип ресурса):

Barbican, Manila, Designate, Magnum, Zun, Trove, Mistral, Aodh, CloudKitty,
Freezer, Blazar, Vitrage, Masakari, Tacker, Adjutant, Watcher, Zaqar, Heat-CFN.

Порты: [ports.md](../ports.md). Операции: [api_coverage.md](../api_coverage.md).

CRUD lifecycle проверяется через `examples/python/openstack_surface_probe.py`
и `tests/openstack/conformance/`.
