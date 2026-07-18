**Language / Язык:** [English](../../domains/octavia.md) | [Русский](octavia.md)

# Octavia (load balancer)

Порт **9876**. Пути под `/v2/lbaas/…`.

## Stateful

Load balancers в `os_loadbalancers`. Listeners/pools/healthmonitors/providers/
flavors обслуживаются из `os_api_objects` (demo seed их заполняет).
