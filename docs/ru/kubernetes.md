**Language / Язык:** [English](../kubernetes.md) | [Русский](kubernetes.md)

# Kubernetes / Helm

Развёртывание опубликованного runtime-образа с Docker Hub чартом
[`helm/openstack-api-simulator`](../../helm/openstack-api-simulator/README.ru.md).

Образ: [`inecs/openstack-api-simulator`](https://hub.docker.com/r/inecs/openstack-api-simulator)

Чарт зеркалирует Docker Compose:

| Компонент | Роль |
|---|---|
| **simulator** Deployment | FastAPI-приложение на `:8080` |
| **api-gateway** Deployment | nginx multi-port шлюз OpenStack |
| **PostgreSQL** StatefulSet | Встроенный Postgres 17 (опционально) |
| **migrate** initContainer | Идемпотентные миграции схемы |
| **seed** Job (опционально) | Лабораторные данные `minimal` или `demo` |

## Требования

- Kubernetes 1.27+ (или аналог)
- Helm 3.14+
- Для Ingress TLS: [Ingress NGINX](https://kubernetes.github.io/ingress-nginx/) и
  [cert-manager](https://cert-manager.io/)

Пример установки cert-manager:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.17.2/cert-manager.yaml
```

## Быстрая установка (Hub release + Ingress + Let's Encrypt)

Из git checkout этого репозитория:

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  -f ./helm/openstack-api-simulator/values-ingress-example.yaml \
  --set certManager.email=you@example.com \
  --set ingress.hosts[0].host=os-sim.example.com \
  --set ingress.tls[0].hosts[0]=os-sim.example.com \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)" \
  --set postgresql.auth.password="$(openssl rand -hex 16)"
```

Что происходит:

1. Скачивается `inecs/openstack-api-simulator:0.1.0`.
2. Устанавливается PostgreSQL 17 (`postgres:17.5-bookworm`).
3. Выполняются миграции схемы в init-контейнере (идемпотентно).
4. Засевается профиль **demo** (`seed.enabled=true`, ~1000 серверов).
5. Разворачивается nginx **api-gateway** со стандартными портами OpenStack (5000, 8774, 9696, …).
6. Создаются ресурсы `ClusterIssuer` (`letsencrypt-prod` / `letsencrypt-staging`).
7. Создаётся Ingress → gateway `:5000` (Keystone + Web UI) с TLS.

DNS для `os-sim.example.com` должен указывать на Ingress controller. Затем:

```bash
kubectl -n openstack-sim get certificate,ingress,pods
curl -sS https://os-sim.example.com/health/ready
open https://os-sim.example.com/
```

Логин по умолчанию: `admin` / `secret` (проект `demo` или `admin`, домен `Default`).

### Сначала staging (рекомендуется)

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  -f ./helm/openstack-api-simulator/values-ingress-example.yaml \
  --set certManager.email=you@example.com \
  --set certManager.useStaging=true \
  --set ingress.hosts[0].host=os-sim.example.com \
  --set ingress.tls[0].hosts[0]=os-sim.example.com \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)"
```

Используйте `curl -k` против staging CA. Для production переключите `certManager.useStaging=false`.

## Минимальная установка (ClusterIP + port-forward)

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)" \
  --set seed.enabled=true \
  --set seed.profile=minimal

kubectl -n openstack-sim port-forward \
  svc/os-sim-openstack-api-simulator-gateway \
  5000:5000 8774:8774 9696:9696 9292:9292 8776:8776
```

| URL | Сервис |
|---|---|
| http://127.0.0.1:5000/ | Keystone + консоль |
| http://127.0.0.1:8774/v2.1/ | Nova |
| http://127.0.0.1:9696/v2.0/ | Neutron |

Полная матрица портов: [ports.md](ports.md).

## Внешний PostgreSQL

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  --set postgresql.enabled=false \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)" \
  --set secret.databaseUrl='postgresql://user:pass@pg.example.com:5432/openstack_simulator'
```

Или `secret.existingSecret` с ключами `DATABASE_URL` и `TICKET_SIGNING_KEY`.

## Как работает api-gateway

Та же модель, что и в Compose (`docker/gateway/openstack-ports.conf`):

1. Клиент подключается к **порту сервиса** (например Nova `8774`).
2. nginx выставляет `X-OpenStack-Service` и `X-Forwarded-Port`.
3. FastAPI переписывает путь в `/_os/<service>/…`, чтобы `/v3` (Keystone vs Cinder) не конфликтовал.

Ingress (если включён) обслуживает **Keystone/UI на порту 5000**. Для Nova/Neutron
извне кластера:

- `kubectl port-forward` дополнительных портов, или
- expose `*-gateway` как `LoadBalancer` / `NodePort` (`gateway.service.type`), или
- дополнительные Ingress rules / TCP-сервисы для этих портов.

## Как выпускается TLS

При `certManager.enabled=true` и `certManager.createClusterIssuer=true` чарт
создаёт ACME `ClusterIssuer` (HTTP-01). Шаблон Ingress добавляет:

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - secretName: openstack-api-simulator-tls
      hosts: [os-sim.example.com]
```

Чарт **не** устанавливает cert-manager или Ingress controller.

## Эксплуатация

```bash
# логи
kubectl -n openstack-sim logs -l app.kubernetes.io/component=simulator -f
kubectl -n openstack-sim logs -l app.kubernetes.io/component=gateway -f

# reseed minimal
kubectl -n openstack-sim exec deploy/os-sim-openstack-api-simulator -- \
  python -m app.openstack.seed_cli --profile minimal

# reseed demo cloud
kubectl -n openstack-sim exec deploy/os-sim-openstack-api-simulator -- \
  python -m app.openstack.seed_cli --profile demo

# активировать серию OpenStack pack
kubectl -n openstack-sim set env deploy/os-sim-openstack-api-simulator \
  OPENSTACK_SERIES=caracal
# затем перезапустить pod / helm upgrade с --set config.openstackSeries=caracal

# удаление
helm -n openstack-sim uninstall os-sim
```

## Справка по values

См. [`helm/openstack-api-simulator/values.yaml`](../../helm/openstack-api-simulator/values.yaml)
и [README чарта](../../helm/openstack-api-simulator/README.ru.md).

Связанные документы:

- [Быстрый старт](getting-started.md) — путь Compose
- [Эксплуатация](operations.md) — публикация на Docker Hub / day-2
- [Порты](ports.md) — матрица портов OpenStack
- [Seed-профили](seed-profiles.md) — `minimal` / `demo`
- [Безопасность](security.md) — лабораторные учётные данные
