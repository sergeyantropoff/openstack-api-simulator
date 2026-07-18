**Language / Язык:** [English](faq.md) | [Русский](ru/faq.md)

# FAQ

## Is this a real OpenStack cloud?

No. It is a **surface-complete API laboratory**: PostgreSQL-backed state,
API-ref-shaped responses, no hypervisor orchestration.

## Which release should I use?

Default **Dalmatian** pack. Switch with `OPENSTACK_SERIES` or the Web UI.
See [api-versions.md](api-versions.md).

## Compose vs Helm?

| Need | Use |
|---|---|
| Local hack / CI on Docker | Compose |
| Cluster + Ingress TLS | Helm ([kubernetes.md](kubernetes.md)) |

## Why so many ports?

OpenStack service catalog expects distinct endpoints. The api-gateway publishes
the [real default port matrix](ports.md) **1:1** (no host remapping).

## Demo cloud wiped my resources

Lifecycle tests and reseed truncate lab tables. Reload with `make seed-demo`.

## Can I point Terraform / Ansible at it?

Yes — use Keystone URL and seeded credentials. Expect lab limitations
(policy, async workflows, Ceph, etc.). See [clients.md](clients.md).

## Where is the Helm chart?

[`helm/openstack-api-simulator`](../helm/openstack-api-simulator) — guide in
[kubernetes.md](kubernetes.md).
