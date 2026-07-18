**Language / Язык:** [English](../clients.md) | [Русский](clients.md)

# Клиенты

## Матрица подключения

| Client | Auth URL | Примечания |
|---|---|---|
| curl | `http://127.0.0.1:5000/v3` | Используйте `X-Subject-Token` → `X-Auth-Token` |
| openstack CLI | `OS_AUTH_URL=…/v3` | См. [authentication.md](authentication.md) |
| openstacksdk | same | Порты service catalog должны совпадать с gateway |
| Terraform OpenStack provider | `auth_url` | Укажите Keystone; catalog направляет Nova/Neutron |
| Ansible `openstack.*` | clouds.yaml | Те же credentials, что и для CLI |

## Compose (локально)

```bash
export OS_AUTH_URL=http://127.0.0.1:5000/v3
export OS_USERNAME=admin
export OS_PASSWORD=secret
export OS_PROJECT_NAME=demo
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_DOMAIN_NAME=Default
export OS_IDENTITY_API_VERSION=3
```

## Helm / Ingress

```bash
export OS_AUTH_URL=https://os-sim.example.com/v3
# Другие сервисы: port-forward портов gateway или catalog URLs,
# которые ваш Ingress/DNS корректно мапят.
```

Для multi-port доступа без Ingress TCP используйте port-forward gateway Service
(см. [kubernetes.md](kubernetes.md)).

## Примеры в репозитории

| Path | Назначение |
|---|---|
| `examples/python/openstack_smoke.py` | Multi-port GET smoke |
| `examples/python/openstack_conformance.py` | Write-path sample |
| `examples/python/openstack_surface_probe.py` | Полный lifecycle probe пакета |

Cookbook'и: [examples/overview.md](examples/overview.md).
