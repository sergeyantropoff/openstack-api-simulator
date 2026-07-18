**Language / Язык:** [English](authentication.md) | [Русский](ru/authentication.md)

# Authentication

The simulator implements **Keystone v3** password authentication and project
scoping (lab subset).

## Password auth

```http
POST /v3/auth/tokens
Content-Type: application/json

{
  "auth": {
    "identity": {
      "methods": ["password"],
      "password": {
        "user": {
          "name": "admin",
          "domain": {"name": "Default"},
          "password": "secret"
        }
      }
    },
    "scope": {
      "project": {"name": "demo", "domain": {"name": "Default"}}
    }
  }
}
```

Response:

- Header **`X-Subject-Token`** — use as **`X-Auth-Token`** on subsequent calls
- Body `token.catalog` — service endpoints (ports match [ports.md](ports.md))

## Seeded principals

Password for all users: **`secret`**. Domain: **`Default`**.

### Minimal seed

| User | Projects | Role |
|---|---|---|
| `admin` | `admin`, `demo` | admin |
| `demo` | `demo` | member |

### Demo cloud

| User | Typical projects |
|---|---|
| `admin` | all |
| `ops` | production, staging |
| `developer` | development, staging |
| `demo` / `auditor` | demo / production |

## Unscoped / errors

- Missing token → `401 Unauthorized`
- Wrong password → `401`
- Project-scoped APIs without project scope → `401` with a clear message

## openstacksdk / CLI

```bash
export OS_AUTH_URL=http://127.0.0.1:5000/v3
export OS_USERNAME=admin
export OS_PASSWORD=secret
export OS_PROJECT_NAME=demo
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_DOMAIN_NAME=Default
export OS_IDENTITY_API_VERSION=3

openstack server list
openstack network list
```

Against Helm Ingress, set `OS_AUTH_URL=https://os-sim.example.com/v3`
(and trust the certificate or use `--insecure` in labs).
