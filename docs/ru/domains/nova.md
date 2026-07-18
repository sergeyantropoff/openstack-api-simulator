**Language / Язык:** [English](../../domains/nova.md) | [Русский](nova.md)

# Nova (compute)

Порт **8774**. Пути под `/v2.1/`.

## Stateful-ресурсы

Servers, flavors, keypairs, server groups, AZ, hypervisors, aggregates,
services, migrations, volume/interface attachments, metadata, tags,
instance actions, consoles (лабораторные URL).

## Demo cloud

~1000 серверов по проектам, metadata/`_tags`, attachments, связанные с volumes
и ports.

## Microversions

Отправляйте `OpenStack-API-Version: compute X.Y` или legacy-заголовок Nova.
Применяются ограничения пакета.
