**Language / Язык:** [English](seed-profiles.md) | [Русский](ru/seed-profiles.md)

# OpenStack seed profiles

| Profile | How to load | Contents |
|---|---|---|
| `minimal` | startup / `make seed` / `python -m app.openstack.seed_cli --profile minimal` | Default domain, admin+demo users, flavors, images, small IaaS sample |
| `demo` | `make seed-demo` / UI Data drawer / Helm `seed.profile=demo` / `--profile demo` | ~1000 servers, 16 hypervisors, 3 AZs, 5 projects, multi-net/SG topology, 600 volumes, ports/FIPs, Octavia/Heat/Ironic/Swift, nested pack samples |

Password for all users: **`secret`**. Domain: **`Default`**.

## Helm

```yaml
seed:
  enabled: true
  profile: demo   # or minimal
```

Post-install Job runs `python -m app.openstack.seed_cli`. Manual reseed:

```bash
kubectl exec deploy/<release>-openstack-api-simulator -- \
  python -m app.openstack.seed_cli --profile demo
```

## Behaviour

Both profiles **truncate** OpenStack lab tables then reload. Prefer `demo` for
density / nested GET probes; `minimal` for fast CI.
