**Language / Язык:** [English](../../examples/troubleshooting-clients.md) | [Русский](troubleshooting-clients.md)

# Устранение неполадок клиентов

## Каталог указывает на недоступные хосты

Seed-каталог в некоторых конфигурациях использует `host.docker.internal` или
имена compose-сервисов. Переопределите endpoints или используйте host gateway,
который вы реально публикуете (`127.0.0.1` с port-forward).

## SSL-ошибки против Ingress

Staging-issuers лаборатории не доверенные — используйте `curl -k` /
`OS_INSECURE=true` только в lab.

## Пустой список серверов

Неверный project scope или demo не загружен. Проверьте:

```bash
openstack project list
make seed-demo
```

## Microversion отклонён

Понизьте запрошенную compute microversion или сбросьте переопределения в Web UI.
