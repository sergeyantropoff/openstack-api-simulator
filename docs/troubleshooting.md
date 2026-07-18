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
