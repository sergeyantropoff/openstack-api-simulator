**Language / Язык:** [English](../authentication.md) | [Русский](authentication.md)

# Аутентификация

Симулятор реализует **Keystone v3** password-аутентификацию и project scoping
(лабораторное подмножество).

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

Ответ:

- Заголовок **`X-Subject-Token`** — используйте как **`X-Auth-Token`** в следующих запросах
- Тело `token.catalog` — endpoints сервисов (порты соответствуют [ports.md](ports.md))

## Seed-принципалы

Пароль для всех пользователей: **`secret`**. Домен: **`Default`**.

### Minimal seed

| Пользователь | Проекты | Роль |
|---|---|---|
| `admin` | `admin`, `demo` | admin |
| `demo` | `demo` | member |

### Demo cloud

| Пользователь | Типичные проекты |
|---|---|
| `admin` | все |
| `ops` | production, staging |
| `developer` | development, staging |
| `demo` / `auditor` | demo / production |

## Unscoped / ошибки

- Нет токена → `401 Unauthorized`
- Неверный пароль → `401`
- Project-scoped API без project scope → `401` с понятным сообщением

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

Против Helm Ingress задайте `OS_AUTH_URL=https://os-sim.example.com/v3`
(и доверьте сертификат или используйте `--insecure` в лаборатории).
