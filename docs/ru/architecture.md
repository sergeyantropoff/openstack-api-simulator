**Language / Язык:** [English](../architecture.md) | [Русский](architecture.md)

# Архитектура

## Компоненты

```
┌─────────────┐     ┌──────────────────┐     ┌────────────┐
│  Clients    │────▶│  api-gateway     │────▶│ simulator  │
│  SDK / CLI  │     │  nginx multi-port│     │ FastAPI    │
│  Web UI     │     │  :5000,:8774,…   │     │ :8080      │
└─────────────┘     └──────────────────┘     └─────┬──────┘
                                                    │
                                              ┌─────▼──────┐
                                              │ PostgreSQL │
                                              └────────────┘
```

| Компонент | Ответственность |
|---|---|
| **api-gateway** | Публикация стандартных портов OpenStack; выставление `X-OpenStack-Service` / `X-Forwarded-Port` |
| **ServiceDispatchMiddleware** | Переписывание в `/_os/<service>/…` |
| **Специализированные роутеры** | Stateful Keystone, Nova, Neutron, Glance, Cinder, Heat, Swift, Ironic, Octavia, Placement |
| **Schema engine** | Surface-complete ops из `contracts/openstack/<series>/` |
| **PostgreSQL** | Identity, IaaS-таблицы, generic store `os_api_objects` |

## Жизненный цикл запроса

1. Клиент обращается, например, к `http://host:8774/v2.1/servers`.
2. Gateway добавляет service headers.
3. Dispatch монтирует запрос под `/_os/nova/…`.
4. Выполняется специализированный Nova handler **или** schema pack operation.
5. Чтение/запись идут в PostgreSQL (типизированные таблицы или `os_api_objects`).

## Contract-пакеты

- Сгенерированный inventory → `contracts/openstack/{yoga,antelope,caracal,dalmatian}/`
- Hot-swap через Web UI / `/ui/api/openstack/contracts/activate`
- Отчёт покрытия: [api_coverage.md](api_coverage.md)

## Seed-профили

| Profile | Содержимое |
|---|---|
| `minimal` | Небольшой Keystone + несколько IaaS-ресурсов |
| `demo` | ~1000 servers, multi-project topology, nested collections |

Подробности: [seed-profiles.md](seed-profiles.md).

## Модель развёртывания

| Mode | Gateway | DB |
|---|---|---|
| Compose | nginx container | bundled Postgres |
| Helm | nginx Deployment + multi-port Service | bundled StatefulSet или external |
| Ingress | TLS terminates at Ingress → gateway:5000 | — |

См. [kubernetes.md](kubernetes.md).
