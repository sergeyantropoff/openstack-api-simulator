**Language / Язык:** [English](schema-services.md) | [Русский](../ru/domains/schema-services.md)

# Schema-backed services

These projects are primarily driven by contract packs + `os_api_objects`
(demo seed inserts multiple rows per resource type):

Barbican, Manila, Designate, Magnum, Zun, Trove, Mistral, Aodh, CloudKitty,
Freezer, Blazar, Vitrage, Masakari, Tacker, Adjutant, Watcher, Zaqar, Heat-CFN.

Ports: [ports.md](../ports.md). Operations: [api_coverage.md](../api_coverage.md).

CRUD lifecycle is exercised by `examples/python/openstack_surface_probe.py`
and `tests/openstack/conformance/`.
