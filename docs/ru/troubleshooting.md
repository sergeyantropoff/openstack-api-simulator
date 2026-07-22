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
- В Web UI HTTP 401 очищает локальную сессию Keystone и показывает **Guest**
  в шапке; войдите снова через Environment

## Ingress отдаёт брендированный HTML 404 / nginx 405 вместо JSON

Симулятор отвечает на ошибки API JSON (`error` / `itemNotFound` / `message`).
Если видите HTML «page not found» или голую страницу nginx **405**, тело
подменил **Ingress / reverse proxy** (часто `custom-http-errors` у
ingress-nginx).

Исправьте annotations Ingress для этого хоста (см.
`helm/openstack-api-simulator/values-ingress-example.yaml`):

```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-intercept-errors: "false"
  nginx.ingress.kubernetes.io/custom-http-errors: "502,503"
```

Проверьте с `Accept: application/json`. Отсутствующий compute instance должен
вернуться JSON (не HTML), например:

```json
{"itemNotFound": {"code": 404, "message": "Instance 'missing-id' could not be found"}}
```

### Корректная authenticated mutation (OpenStack)

Токен Keystone в заголовке и JSON-тело (OpenStack API — JSON, не
form-urlencoded):

```bash
# после POST /v3/auth/tokens → X-Subject-Token
TOKEN=...
curl -sS -X POST "https://HOST:8774/v2.1/servers" \
  -H "X-Auth-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"server":{"name":"demo","flavorRef":"...","imageRef":"...","networks":[{"uuid":"..."}]}}'
```

Keystone/UI через Ingress обычно `:443→5000`; порты Nova и других сервисов
по-прежнему нуждаются в port-forward / LoadBalancer / TCP Ingress, если вы не
ходите через multi-port gateway Service.

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
