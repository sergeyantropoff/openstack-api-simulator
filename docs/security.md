**Language / Язык:** [English](security.md) | [Русский](ru/security.md)

# Security

This project is a **laboratory simulator**, not a production OpenStack cloud.

## Trust boundary

- Default passwords (`secret`) are intentional for labs.
- `TICKET_SIGNING_KEY` / `secret.ticketSigningKey` must be rotated before any
  shared or internet-facing deployment.
- Bundled Postgres passwords in values/compose are lab defaults.

## Network exposure

| Surface | Risk |
|---|---|
| Compose ports on `0.0.0.0` | Entire API surface reachable on the host |
| Helm Ingress | Public HTTPS to Keystone/UI; other OS ports need explicit exposure |
| Read-only root FS (Helm) | Reduces container write surface |

## TLS

- Compose: optional nginx TLS on `:443` with lab cert under `docker/tls/`
- Helm: terminate TLS at Ingress + cert-manager (recommended)

## What is not implemented

- Real Keystone federation / Fernet key rotation semantics
- oslo.policy rule parity
- Multi-tenant isolation beyond project_id filters in handlers

Treat all data as disposable lab fixtures.
