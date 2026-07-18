**Language / Язык:** [English](kubernetes.md) | [Русский](ru/kubernetes.md)

# Kubernetes / Helm

Deploy the published Docker Hub runtime image with the chart in
[`helm/openstack-api-simulator`](../helm/openstack-api-simulator).

Image: [`inecs/openstack-api-simulator`](https://hub.docker.com/r/inecs/openstack-api-simulator)

The chart mirrors Docker Compose:

| Component | Role |
|---|---|
| **simulator** Deployment | FastAPI app on `:8080` |
| **api-gateway** Deployment | nginx multi-port OpenStack gateway |
| **PostgreSQL** StatefulSet | Bundled Postgres 17 (optional) |
| **migrate** initContainer | Idempotent schema migrations |
| **seed** Job (optional) | `minimal` or `demo` lab data |

## Prerequisites

- Kubernetes 1.27+ (or comparable)
- Helm 3.14+
- For Ingress TLS: [Ingress NGINX](https://kubernetes.github.io/ingress-nginx/) and
  [cert-manager](https://cert-manager.io/)

Example cert-manager install:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.17.2/cert-manager.yaml
```

## Quick install (Hub release + Ingress + Let's Encrypt)

From a git checkout of this repository:

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

What this does:

1. Pulls `inecs/openstack-api-simulator:0.1.0`.
2. Installs bundled PostgreSQL 17 (`postgres:17.5-bookworm`).
3. Runs schema migrations in an init container (idempotent).
4. Seeds the **demo** lab profile (`seed.enabled=true`, ~1000 servers).
5. Deploys nginx **api-gateway** with OpenStack default ports (5000, 8774, 9696, …).
6. Creates `ClusterIssuer` resources (`letsencrypt-prod` / `letsencrypt-staging`).
7. Creates an Ingress → gateway `:5000` (Keystone + Web UI) with TLS.

DNS for `os-sim.example.com` must point at your Ingress controller. Then:

```bash
kubectl -n openstack-sim get certificate,ingress,pods
curl -sS https://os-sim.example.com/health/ready
open https://os-sim.example.com/
```

Default seeded login: `admin` / `secret` (project `demo` or `admin`, domain `Default`).

### Staging first (recommended)

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

Use `curl -k` against the staging CA. Flip `certManager.useStaging=false` for production.

## Minimal install (ClusterIP + port-forward)

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

| URL | Service |
|---|---|
| http://127.0.0.1:5000/ | Keystone + console |
| http://127.0.0.1:8774/v2.1/ | Nova |
| http://127.0.0.1:9696/v2.0/ | Neutron |

Full port matrix: [ports.md](ports.md).

## External PostgreSQL

```bash
helm upgrade --install os-sim ./helm/openstack-api-simulator \
  -n openstack-sim --create-namespace \
  --set postgresql.enabled=false \
  --set secret.ticketSigningKey="$(openssl rand -hex 32)" \
  --set secret.databaseUrl='postgresql://user:pass@pg.example.com:5432/openstack_simulator'
```

Or use `secret.existingSecret` with keys `DATABASE_URL` and `TICKET_SIGNING_KEY`.

## How the api-gateway works

Same model as Compose (`docker/gateway/openstack-ports.conf`):

1. Client connects to a **service-specific port** (e.g. Nova `8774`).
2. nginx sets `X-OpenStack-Service` and `X-Forwarded-Port`.
3. FastAPI rewrites to `/_os/<service>/…` so `/v3` (Keystone vs Cinder) does not collide.

Ingress (when enabled) fronts **Keystone/UI on port 5000**. For Nova/Neutron from
outside the cluster, either:

- `kubectl port-forward` additional ports, or
- expose `*-gateway` as `LoadBalancer` / `NodePort` (`gateway.service.type`), or
- add extra Ingress rules / TCP services for those ports.

## How TLS issuance works

When `certManager.enabled=true` and `certManager.createClusterIssuer=true`, the
chart creates ACME `ClusterIssuer` objects (HTTP-01). The Ingress template adds:

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - secretName: openstack-api-simulator-tls
      hosts: [os-sim.example.com]
```

The chart does **not** install cert-manager or the Ingress controller.

## Operations

```bash
# logs
kubectl -n openstack-sim logs -l app.kubernetes.io/component=simulator -f
kubectl -n openstack-sim logs -l app.kubernetes.io/component=gateway -f

# reseed minimal
kubectl -n openstack-sim exec deploy/os-sim-openstack-api-simulator -- \
  python -m app.openstack.seed_cli --profile minimal

# reseed demo cloud
kubectl -n openstack-sim exec deploy/os-sim-openstack-api-simulator -- \
  python -m app.openstack.seed_cli --profile demo

# activate OpenStack pack series
kubectl -n openstack-sim set env deploy/os-sim-openstack-api-simulator \
  OPENSTACK_SERIES=caracal
# then restart the pod / helm upgrade with --set config.openstackSeries=caracal

# uninstall
helm -n openstack-sim uninstall os-sim
```

## Values reference

See [`helm/openstack-api-simulator/values.yaml`](../helm/openstack-api-simulator/values.yaml)
and the [chart README](../helm/openstack-api-simulator/README.md).

Related docs:

- [Getting started](getting-started.md) — Compose path
- [Operations](operations.md) — Docker Hub publish / day-2
- [Ports](ports.md) — OpenStack port matrix
- [Seed profiles](seed-profiles.md) — `minimal` / `demo`
- [Security](security.md) — lab credentials
