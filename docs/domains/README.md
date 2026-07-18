**Language / Язык:** [English](README.md) | [Русский](../ru/domains/README.md)

# OpenStack service domains

Guides for the main specialized surfaces. Pack-only services (Barbican, Manila,
Designate, …) are covered generically by the schema engine and seeded into
`os_api_objects` — see [api-surface.md](../api-surface.md) and
[api_coverage.md](../api_coverage.md).

| Guide | Service | Port |
|---|---|---|
| [keystone.md](keystone.md) | Identity | 5000 |
| [nova.md](nova.md) | Compute | 8774 |
| [neutron.md](neutron.md) | Network | 9696 |
| [glance.md](glance.md) | Image | 9292 |
| [cinder.md](cinder.md) | Block storage | 8776 |
| [placement.md](placement.md) | Placement | 8003 |
| [heat.md](heat.md) | Orchestration | 8004 |
| [swift.md](swift.md) | Object storage | 8080 |
| [ironic.md](ironic.md) | Bare metal | 6385 |
| [octavia.md](octavia.md) | Load balancer | 9876 |
| [schema-services.md](schema-services.md) | Remaining pack services | various |
