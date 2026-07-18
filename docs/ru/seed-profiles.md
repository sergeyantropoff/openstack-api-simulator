**Language / Язык:** [English](../seed-profiles.md) | [Русский](seed-profiles.md)

# Seed-профили OpenStack

| Profile | Как загрузить | Содержимое |
|---|---|---|
| `minimal` | startup / `make seed` / `python -m app.openstack.seed_cli --profile minimal` | Default domain, admin+demo users, flavors, images, небольшой IaaS sample |
| `demo` | `make seed-demo` / UI Data drawer / Helm `seed.profile=demo` / `--profile demo` | ~1000 servers, 16 hypervisors, 3 AZs, 5 projects, multi-net/SG topology, 600 volumes, ports/FIPs, Octavia/Heat/Ironic/Swift, nested pack samples |

Пароль для всех пользователей: **`secret`**. Домен: **`Default`**.

## Helm

```yaml
seed:
  enabled: true
  profile: demo   # or minimal
```

Post-install Job запускает `python -m app.openstack.seed_cli`. Ручной reseed:

```bash
kubectl exec deploy/<release>-openstack-api-simulator -- \
  python -m app.openstack.seed_cli --profile demo
```

## Поведение

Оба профиля **очищают** лабораторные таблицы OpenStack и перезагружают данные.
Предпочитайте `demo` для плотности / nested GET probes; `minimal` для быстрого CI.
