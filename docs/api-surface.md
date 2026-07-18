**Language / Язык:** [English](api-surface.md) | [Русский](ru/api-surface.md)

# API surface

## Surface-complete packs

Each OpenStack series pack lists **method + path** operations. At startup every
unique `(method, path)` is registered as its own FastAPI route (`os-contract:…`),
Proxmox-style. Stateful handlers from specialized modules are looked up via a
`HandlerRegistry`; everything else falls through to the schema engine
(`os_api_objects` lab JSON).

| Series | Services | Operations (approx.) |
|---|---|---|
| Yoga | 28 | ~1060 |
| Antelope | 28 | ~1108 |
| Caracal | 28 | ~1196 |
| Dalmatian | 28 | ~1357 |

Authoritative numbers: [api_coverage.md](api_coverage.md).

## Handlers vs schema fallback

| Layer | Services / resources |
|---|---|
| **Specialized handlers** | Keystone tokens/catalog, Nova servers/flavors/keypairs/…, Neutron nets/ports/…, Glance images, Cinder volumes, Heat stacks, Swift, Ironic nodes, Octavia LBs, Placement RPs |
| **Schema fallback** | Remaining pack collections (Barbican, Manila, Designate, Magnum, …) including nested paths |

## Microversions

Headers such as `OpenStack-API-Version: compute 2.79` and
`X-OpenStack-Nova-API-Version` are accepted and gated per pack metadata.
Overrides can be set in the Web UI Environment drawer.

## Actions

Nova-style `POST /servers/{id}/action` and similar pack `kind=action` ops are
handled by the schema/action path (power state updates for common actions).

## Errors

OpenStack-shaped errors (`OpenStackError`) with `code`, `title`, `message`.
Unknown routes that are not in the active contract pack return standard
FastAPI `404`.
