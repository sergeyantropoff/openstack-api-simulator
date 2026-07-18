**Language / Язык:** [English](../../domains/keystone.md) | [Русский](keystone.md)

# Keystone (identity)

Порт **5000**. Пути под `/v3/`.

## Реализовано (lab)

- `POST /v3/auth/tokens` — password auth, project scope
- Catalog с multi-port endpoints
- Projects, users, roles, role assignments (seed + CRUD через pack/schema)
- Domains (`Default`)

## Seed

Профили minimal и demo создают домен `Default`, роли `admin`/`member` и
пользователей, описанных в [authentication.md](../authentication.md).

## Примечания

Federation, application credentials и полный policy engine вне scope.
