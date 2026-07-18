**Language / Язык:** [English](../api_coverage.md) | [Русский](api_coverage.md)

# Покрытие OpenStack API — dalmatian

Сгенерировано из `contracts/openstack/dalmatian/manifest.json`.

- **Services:** 28
- **Operations:** 1357
- **Checksum:** `5d8f32baa835db2b556b6f33ac3c1b67b74db8194f00ce7d6eb8c59e3bbd7063`
- **Generated at:** 2026-07-16T00:28:30Z

## Дельты серий

| Series | Major | Operations |
|---|---:|---:|
| Antelope | 7 | 1108 |
| Caracal | 8 | 1196 |
| Dalmatian | 9 | 1357 |
| Yoga | 6 | 1060 |

Более старые серии опускают пути, добавленные позже (`tools/os_api_inventory/series_deltas.py`),
и используют более низкие потолки microversion. Примените пакет в API catalog drawer для hot-swap.

Surface-complete означает, что каждая операция пакета смонтирована schema-движком
(специализированные роутеры по-прежнему выигрывают на пересекающихся stateful-путях).

| Service | Type | Port | Operations | Microversions |
|---|---|---:|---:|---|
| adjutant | admin-logic | 5050 | 24 | — |
| aodh | alarming | 8042 | 19 | — |
| barbican | key-manager | 9311 | 25 | — |
| blazar | reservation | 1234 | 19 | — |
| cinder | volumev3 | 8776 | 98 | 3.0–3.70 |
| cloudkitty | rating | 8889 | 25 | — |
| designate | dns | 9001 | 37 | — |
| freezer | backup | 9090 | 31 | — |
| glance | image | 9292 | 39 | — |
| heat | orchestration | 8004 | 38 | — |
| heat-cfn | cloudformation | 8000 | 8 | — |
| ironic | baremetal | 6385 | 58 | 1.1–1.90 |
| keystone | identity | 5000 | 77 | — |
| magnum | container-infra | 9511 | 25 | — |
| manila | sharev2 | 8786 | 50 | 2.0–2.82 |
| masakari | instance-ha | 15868 | 19 | — |
| mistral | workflowv2 | 8989 | 37 | — |
| neutron | network | 9696 | 290 | — |
| nova | compute | 8774 | 124 | 2.1–2.96 |
| octavia | load-balancer | 9876 | 74 | — |
| placement | placement | 8003 | 30 | 1.0–1.39 |
| swift | object-store | 8080 | 10 | — |
| tacker | nfv-orchestration | 9890 | 30 | — |
| trove | database | 8779 | 31 | — |
| vitrage | rca | 8999 | 30 | — |
| watcher | infra-optim | 9322 | 49 | — |
| zaqar | messaging | 8888 | 27 | — |
| zun | container | 9517 | 33 | — |

## Минимумы core

| Service | Required | Actual |
|---|---:|---:|
| keystone | 40 | 77 (OK) |
| neutron | 70 | 290 (OK) |
| nova | 70 | 124 (OK) |
