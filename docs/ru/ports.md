**Language / Язык:** [English](../ports.md) | [Русский](ports.md)

# Стандартные порты OpenStack в этом симуляторе

Справка: [Firewalls and default ports](https://docs.openstack.org/install-guide/firewalls-default-ports.html).

Это **реальные публичные порты API OpenStack по умолчанию**. Compose и Helm
публикуют их **один в один** на хосте / Service (без смещения): хост `5000` —
Keystone, хост `8774` — Nova и т.д. Запускайте стек на отдельном хосте/ВМ,
чтобы эти порты не пересекались с другими лабораторными симуляторами.

Клиенты обращаются к **api-gateway** (nginx) — сервис Compose или Helm
Deployment/Service `*-gateway`. На каждом listen-порту выставляются
`X-OpenStack-Service` и `X-Forwarded-Port`; процесс FastAPI переписывает путь в
`/_os/<service>/…`, чтобы пересекающиеся корни API (`/v3`, `/v1`, …) не конфликтовали.

Типичный auth URL: `http://127.0.0.1:5000/v3` (или HTTPS на `:5000` / `:443`
через gateway).

Список в Helm values: `gateway.service.ports` в
[`helm/openstack-api-simulator/values.yaml`](../../helm/openstack-api-simulator/values.yaml).

| Порт | Сервис | За что отвечает | Основные пути |
|------|--------|-----------------|---------------|
| 5000 | keystone | Identity — токены, проекты, пользователи, роли, service catalog | `/v3/auth/tokens`, `/v3/projects`, … |
| 8774 | nova | Compute — серверы (ВМ), flavors, keypairs, AZ, hypervisors | `/v2.1/servers`, flavors, keypairs, AZ, hypervisors, … |
| 9696 | neutron | Network — сети, подсети, порты, роутеры, SG, floating IP | `/v2.0/networks`, subnets, ports, routers, SG, FIPs, QoS, trunks, … |
| 9292 | glance | Image — образы | `/v2/images` |
| 8776 | cinder | Block storage — тома, снапшоты, типы томов | `/v3/volumes` |
| 8003 | placement | Placement — resource providers и inventories | `/resource_providers` |
| 8004 | heat | Orchestration — стеки Heat | `/v1/{project_id}/stacks` |
| 8000 | heat-cfn | CloudFormation-совместимый API Heat | `/stacks` |
| 8080 | swift | Object storage — аккаунты, контейнеры, объекты | `/v1/{account}/{container}/…`, `/info` |
| 6385 | ironic | Bare metal — ноды, порты, chassis | `/v1/nodes` |
| 9876 | octavia | Load balancing — балансировщики, listeners, pools | `/v2/lbaas/loadbalancers` |
| 9311 | barbican | Key manager — секреты, контейнеры | `/v1/secrets` |
| 8786 | manila | Shared file systems — shares | `/v2/shares` |
| 9001 | designate | DNS — зоны и recordsets | `/v2/zones` |
| 9511 | magnum | Container infra — кластеры (например Kubernetes) | `/v1/clusters` |
| 9517 | zun | Containers — жизненный цикл контейнеров | `/v1/containers` |
| 8779 | trove | Database as a service — экземпляры БД | `/v1.0/instances` |
| 8989 | mistral | Workflows | `/v2/workflows` |
| 8042 | aodh | Alarming — алармы | `/v2/alarms` |
| 8889 | cloudkitty | Rating / биллинг-метрики | `/v1/rating/…` |
| 9090 | freezer | Backup — задания резервного копирования | `/v2/jobs` |
| 1234 | blazar | Reservation — leases | `/leases` |
| 8999 | vitrage | Root cause analysis (RCA) | `/v1/alarm` |
| 15868 | masakari | Instance HA — высокая доступность инстансов | `/v1/segments` |
| 9890 | tacker | NFV orchestration | `/v1.0/vnfs` |
| 5050 | adjutant | Admin workflows / self-service задачи | `/v1/tasks` |
| 9322 | watcher | Infrastructure optimization | `/v1/…` |
| 8888 | zaqar | Messaging | `/v2/…` |
| 80 | http | Reverse proxy консоли (Compose + Helm gateway) | — |
| 443 | https | TLS reverse proxy (**только Compose**; в Helm TLS завершается на Ingress) | — |

Внутренний FastAPI слушает `8080` только внутри Docker (не Swift public port с хоста — хост `8080` это Swift через gateway). Postgres публикуется только как `127.0.0.1:5433` (это не порт OpenStack API).
