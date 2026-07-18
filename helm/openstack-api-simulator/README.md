**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Helm chart: openstack-api-simulator

Deploys the published runtime image
[`inecs/openstack-api-simulator`](https://hub.docker.com/r/inecs/openstack-api-simulator)
with bundled PostgreSQL, migrations, optional seed Job, multi-port nginx
**api-gateway**, Ingress, and cert-manager Let's Encrypt `ClusterIssuer` resources.

Full guide: [docs/kubernetes.md](../../docs/kubernetes.md).

## Quick install

Prerequisites: Kubernetes, Helm 3, ingress-nginx (or compatible), cert-manager
(for TLS example).

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

Point DNS at the Ingress controller, wait for Certificate Ready, then open
`https://os-sim.example.com/`.

Minimal ClusterIP + port-forward:

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)" \
  --set seed.enabled=true --set seed.profile=minimal

kubectl -n openstack-sim port-forward \
  svc/os-sim-openstack-api-simulator-gateway \
  5000:5000 8774:8774 9696:9696 9292:9292 8776:8776
```

## Values overview

| Key | Default | Meaning |
|---|---|---|
| `image.repository` | `inecs/openstack-api-simulator` | Hub image |
| `image.tag` | chart `appVersion` | Image tag |
| `gateway.enabled` | `true` | Multi-port nginx OpenStack gateway |
| `gateway.service.ports` | 5000, 8774, 9696, … | Published API ports |
| `postgresql.enabled` | `true` | Bundle official PostgreSQL StatefulSet |
| `migrate.enabled` | `true` | Schema migrate initContainer |
| `seed.enabled` | `false` | Post-install seed Job |
| `seed.profile` | `minimal` | `minimal` or `demo` |
| `ingress.enabled` | `false` | Expose Keystone/UI via Ingress |
| `certManager.enabled` | `false` | Annotate Ingress + optional ClusterIssuers |

See [`values.yaml`](values.yaml) and [`values-ingress-example.yaml`](values-ingress-example.yaml).

## Chart layout

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

Validate locally:

```bash
helm lint ./helm/openstack-api-simulator
helm template os-sim ./helm/openstack-api-simulator --set secret.ticketSigningKey=test
```

## Integration suites

Hypervisor-lab / API coverage tests (`pulumi-tests/`) run via **Docker Compose**, not this chart.
Deploy the simulator with Helm, then point host-side or CI runners at the gateway
Service (port-forward or LoadBalancer). See [docs/hypervisor-lab.md](../../docs/hypervisor-lab.md).
