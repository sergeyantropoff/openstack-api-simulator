**Language / Язык:** [English](nova.md) | [Русский](../ru/domains/nova.md)

# Nova (compute)

Port **8774**. Paths under `/v2.1/`.

## Stateful resources

Servers, flavors, keypairs, server groups, AZ, hypervisors, aggregates,
services, migrations, volume/interface attachments, metadata, tags,
instance actions, consoles (lab URLs).

## Demo cloud

~1000 servers across projects, metadata/`_tags`, attachments linked to volumes
and ports.

## Microversions

Send `OpenStack-API-Version: compute X.Y` or Nova legacy header. Pack gates apply.
