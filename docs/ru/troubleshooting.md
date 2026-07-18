**Language / Язык:** [English](../troubleshooting.md) | [Русский](troubleshooting.md)

# Устранение неполадок

## `/health/ready` возвращает 503

- Postgres не поднят или неверный `DATABASE_URL`
- Миграции не применены — проверьте migrate initContainer / `make db-migrate`
- Helm: `kubectl logs` на pod simulator (migrate init)

## Auth 401

- Неверный user/password/domain (`Default`)
- Отсутствует project scope для project-scoped API
- Токен от другого экземпляра simulator (reseed меняет ID)

## Пустые списки после lifecycle probe

Lifecycle DELETE может удалить demo-scoped строки. Перезагрузите:

```bash
make seed-demo
# or Helm:
kubectl exec deploy/… -- python -m app.openstack.seed_cli --profile demo
```

## Неверный сервис отвечает на порту

Проверьте gateway headers:

```bash
curl -sI http://127.0.0.1:8774/ | grep -i openstack
```

Ожидайте `X-OpenStack-Service: nova`. Если обращаетесь к simulator `:8080` напрямую,
задайте `X-OpenStack-Route-Service` / `X-OpenStack-Service` сами.

## Helm port-forward на 5000 не работает

Forward **gateway** Service, а не simulator Service:

```bash
kubectl port-forward svc/<release>-openstack-api-simulator-gateway 5000:5000
```

## Pack activate 404 / пустые ops

Убедитесь, что `contracts/openstack/<series>/` есть в образе и
`OPENSTACK_SERIES` — известное имя серии.

## Порты catalog недоступны клиенту

Catalog рекламирует per-service порты. При только Ingress на `:443→5000` Nova
`:8774` не публикуется автоматически. Используйте port-forward или expose gateway
Service (см. [kubernetes.md](kubernetes.md)).
