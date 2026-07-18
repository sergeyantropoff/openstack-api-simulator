**Language / Язык:** [English](keystone.md) | [Русский](../ru/domains/keystone.md)

# Keystone (identity)

Port **5000**. Paths under `/v3/`.

## Implemented (lab)

- `POST /v3/auth/tokens` — password auth, project scope
- Catalog with multi-port endpoints
- Projects, users, roles, role assignments (seeded + CRUD via pack/schema)
- Domains (Default)

## Seed

Minimal and demo profiles create `Default` domain, roles `admin`/`member`, and
users documented in [authentication.md](../authentication.md).

## Notes

Federation, application credentials, and full policy engine are out of scope.
