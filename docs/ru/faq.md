**Language / Язык:** [English](../faq.md) | [Русский](faq.md)

# FAQ

## Это настоящее OpenStack cloud?

Нет. Это **surface-complete API laboratory**: состояние в PostgreSQL,
ответы в форме API-ref, без оркестрации гипервизора.

## Какой релиз использовать?

По умолчанию пакет **Dalmatian**. Переключайте через `OPENSTACK_SERIES` или Web UI.
См. [api-versions.md](api-versions.md).

## Compose vs Helm?

| Need | Use |
|---|---|
| Local hack / CI on Docker | Compose |
| Cluster + Ingress TLS | Helm ([kubernetes.md](kubernetes.md)) |

## Зачем так много портов?

Service catalog OpenStack ожидает отдельные endpoints. api-gateway публикует
[реальную матрицу портов по умолчанию](ports.md) **один в один** (без смещения на хосте).

## Demo cloud стёр мои ресурсы

Lifecycle-тесты и reseed очищают lab tables. Перезагрузите через `make seed-demo`.

## Можно ли направить Terraform / Ansible сюда?

Да — используйте Keystone URL и seed credentials. Ожидайте lab limitations
(policy, async workflows, Ceph и т.д.). См. [clients.md](clients.md).

## Где Helm chart?

[`helm/openstack-api-simulator`](../../helm/openstack-api-simulator/README.ru.md) — руководство в
[kubernetes.md](kubernetes.md).
