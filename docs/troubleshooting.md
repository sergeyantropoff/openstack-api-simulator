**Language / Язык:** [English](troubleshooting.md) | [Русский](ru/troubleshooting.md)

# Troubleshooting

## `/health/ready` is 503

- Postgres not up or wrong `DATABASE_URL`
- Migrations not applied — check migrate initContainer / `make db-migrate`
- Helm: `kubectl logs` on the simulator pod (migrate init)

## Auth 401

- Wrong user/password/domain (`Default`)
- Project scope missing for project-scoped APIs
- Token from a different simulator instance (reseed rotates IDs)
- In the Web UI, HTTP 401 clears the local Keystone session and shows **Guest**
  in the header; sign in again from Environment

## Ingress returns branded HTML 404 / nginx 405 instead of JSON

The simulator answers API errors as JSON (`error` / `itemNotFound` / `message`).
If you see a site HTML “page not found” or plain nginx **405** page, the
**Ingress / reverse proxy** replaced the upstream body (often via
`custom-http-errors` on the ingress-nginx controller).

Fix on the Ingress for this host (see
`helm/openstack-api-simulator/values-ingress-example.yaml`):

```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-intercept-errors: "false"
  nginx.ingress.kubernetes.io/custom-http-errors: "502,503"
```

Then re-check with `Accept: application/json`. A missing compute instance should
look like JSON (not HTML), for example:

```json
{"itemNotFound": {"code": 404, "message": "Instance 'missing-id' could not be found"}}
```

### Correct authenticated mutation (OpenStack)

Use a Keystone token header and JSON body (OpenStack APIs are JSON, not
form-urlencoded):

```bash
# after POST /v3/auth/tokens → X-Subject-Token
TOKEN=...
curl -sS -X POST "https://HOST:8774/v2.1/servers" \
  -H "X-Auth-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"server":{"name":"demo","flavorRef":"...","imageRef":"...","networks":[{"uuid":"..."}]}}'
```

Keystone/UI via Ingress is usually `:443→5000`; Nova and other service ports
still need port-forward / LoadBalancer / TCP Ingress unless you only call
through the multi-port gateway Service.

## Empty lists after lifecycle probe

Lifecycle DELETE can remove demo-scoped rows. Reload:

```bash
make seed-demo
# or Helm:
kubectl exec deploy/… -- python -m app.openstack.seed_cli --profile demo
```

## Wrong service answers on a port

Confirm gateway headers:

```bash
curl -sI http://127.0.0.1:8774/ | grep -i openstack
```

Expect `X-OpenStack-Service: nova`. If you hit simulator `:8080` directly,
set `X-OpenStack-Route-Service` / `X-OpenStack-Service` yourself.

## Helm port-forward to 5000 fails

Forward the **gateway** Service, not the simulator Service:

```bash
kubectl port-forward svc/<release>-openstack-api-simulator-gateway 5000:5000
```

## Pack activate 404 / empty ops

Ensure `contracts/openstack/<series>/` exists in the image and
`OPENSTACK_SERIES` is a known series name.

## Client catalog ports unreachable

Catalog advertises per-service ports. With only Ingress on `:443→5000`, Nova
`:8774` is not automatically published. Port-forward or expose the gateway
Service (see [kubernetes.md](kubernetes.md)).
