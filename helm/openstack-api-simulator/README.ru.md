**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Helm chart: openstack-api-simulator

Разворачивает опубликованный runtime-образ
[`inecs/openstack-api-simulator`](https://hub.docker.com/r/inecs/openstack-api-simulator)
со встроенным PostgreSQL, миграциями, опциональным seed Job, multi-port nginx
**api-gateway**, Ingress и ресурсами cert-manager Let's Encrypt `ClusterIssuer`.

Полное руководство: [docs/ru/kubernetes.md](../../docs/ru/kubernetes.md).

## Быстрая установка

Требования: Kubernetes, Helm 3, ingress-nginx (или совместимый), cert-manager
(для TLS-примера).

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

Укажите DNS на Ingress controller, дождитесь Certificate Ready, затем откройте
`https://os-sim.example.com/`.

Минимальный ClusterIP + port-forward:

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)" \
  --set seed.enabled=true --set seed.profile=minimal

kubectl -n openstack-sim port-forward \
  svc/os-sim-openstack-api-simulator-gateway \
  5000:5000 8774:8774 9696:9696 9292:9292 8776:8776
```

## Обзор values

| Ключ | По умолчанию | Смысл |
|---|---|---|
| `image.repository` | `inecs/openstack-api-simulator` | Образ на Hub |
| `image.tag` | chart `appVersion` | Тег образа |
| `gateway.enabled` | `true` | Multi-port nginx шлюз OpenStack |
| `gateway.service.ports` | 5000, 8774, 9696, … | Публикуемые порты API |
| `postgresql.enabled` | `true` | Встроенный PostgreSQL StatefulSet |
| `migrate.enabled` | `true` | initContainer миграций схемы |
| `seed.enabled` | `false` | Post-install seed Job |
| `seed.profile` | `minimal` | `minimal` или `demo` |
| `ingress.enabled` | `false` | Keystone/UI через Ingress |
| `certManager.enabled` | `false` | Аннотации Ingress + опциональные ClusterIssuers |

См. [`values.yaml`](values.yaml) и [`values-ingress-example.yaml`](values-ingress-example.yaml).

## Структура чарта

```text
helm/openstack-api-simulator/
  Chart.yaml
  values.yaml
  values-ingress-example.yaml
  templates/
    deployment.yaml          # simulator (FastAPI :8080)
    gateway-deployment.yaml  # nginx multi-port gateway
    gateway-service.yaml
    gateway-configmap.yaml
    postgresql-statefulset.yaml
    migrate-job.yaml / initContainer
    seed-job.yaml
    ingress.yaml
    clusterissuer.yaml
    secret.yaml
    NOTES.txt
```

Локальная проверка:

```bash
helm lint ./helm/openstack-api-simulator
helm template os-sim ./helm/openstack-api-simulator --set secret.ticketSigningKey=test
```

## Интеграционные сьюты

Тесты покрытия API (`pulumi-tests/`) запускаются через **Docker Compose**, не через этот чарт.
Разверните симулятор Helm'ом, затем направьте host/CI runners на gateway
Service (port-forward или LoadBalancer). См. [docs/ru/hypervisor-lab.md](../../docs/ru/hypervisor-lab.md).
