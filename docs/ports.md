**Language / Язык:** [English](ports.md) | [Русский](ru/ports.md)

# OpenStack default ports in this simulator

Reference: [Firewalls and default ports](https://docs.openstack.org/install-guide/firewalls-default-ports.html).

These are the **real OpenStack public API defaults**. Compose and Helm publish
them **1:1** on the host / Service (no remapping): host `5000` is Keystone,
host `8774` is Nova, and so on. Run this stack on its own host/VM so these
ports do not collide with other lab simulators.

Clients talk to **api-gateway** (nginx) — Compose service or Helm
`*-gateway` Deployment/Service. Each listen port sets `X-OpenStack-Service`
and `X-Forwarded-Port`; the FastAPI process rewrites the path to
`/_os/<service>/…` so overlapping API roots (`/v3`, `/v1`, …) do not collide.

Typical auth URL: `http://127.0.0.1:5000/v3` (or HTTPS on `:5000` / `:443`
via the gateway).

Helm values list: `gateway.service.ports` in
[`helm/openstack-api-simulator/values.yaml`](../helm/openstack-api-simulator/values.yaml).

| Port | Service | Role | Primary paths |
|------|---------|------|---------------|
| 5000 | keystone | Identity — tokens, projects, users, roles, service catalog | `/v3/auth/tokens`, `/v3/projects`, … |
| 8774 | nova | Compute — servers (VMs), flavors, keypairs, AZ, hypervisors | `/v2.1/servers`, flavors, keypairs, AZ, hypervisors, … |
| 9696 | neutron | Network — networks, subnets, ports, routers, SG, floating IPs | `/v2.0/networks`, subnets, ports, routers, SG, FIPs, QoS, trunks, … |
| 9292 | glance | Image — glance images | `/v2/images` |
| 8776 | cinder | Block storage — volumes, snapshots, volume types | `/v3/volumes` |
| 8003 | placement | Placement — resource providers and inventories | `/resource_providers` |
| 8004 | heat | Orchestration — Heat stacks | `/v1/{project_id}/stacks` |
| 8000 | heat-cfn | CloudFormation-compatible Heat API | `/stacks` |
| 8080 | swift | Object storage — accounts, containers, objects | `/v1/{account}/{container}/…`, `/info` |
| 6385 | ironic | Bare metal — nodes, ports, chassis | `/v1/nodes` |
| 9876 | octavia | Load balancing — load balancers, listeners, pools | `/v2/lbaas/loadbalancers` |
| 9311 | barbican | Key manager — secrets, containers | `/v1/secrets` |
| 8786 | manila | Shared file systems — shares | `/v2/shares` |
| 9001 | designate | DNS — zones and recordsets | `/v2/zones` |
| 9511 | magnum | Container infra — clusters (e.g. Kubernetes) | `/v1/clusters` |
| 9517 | zun | Containers — container lifecycle | `/v1/containers` |
| 8779 | trove | Database as a service — DB instances | `/v1.0/instances` |
| 8989 | mistral | Workflows | `/v2/workflows` |
| 8042 | aodh | Alarming | `/v2/alarms` |
| 8889 | cloudkitty | Rating / billing metering | `/v1/rating/…` |
| 9090 | freezer | Backup jobs | `/v2/jobs` |
| 1234 | blazar | Reservation — leases | `/leases` |
| 8999 | vitrage | Root cause analysis (RCA) | `/v1/alarm` |
| 15868 | masakari | Instance high availability | `/v1/segments` |
| 9890 | tacker | NFV orchestration | `/v1.0/vnfs` |
| 5050 | adjutant | Admin workflows / self-service tasks | `/v1/tasks` |
| 9322 | watcher | Infrastructure optimization | `/v1/…` |
| 8888 | zaqar | Messaging | `/v2/…` |
| 80 | http | Console UI reverse proxy (Compose + Helm gateway) | — |
| 443 | https | TLS reverse proxy (**Compose only**; Helm terminates TLS at Ingress) | — |

Internal FastAPI listens on `8080` inside Docker only (not the Swift public port from the host — host `8080` is Swift via gateway). Postgres is published only as `127.0.0.1:5433` (not an OpenStack API port).
