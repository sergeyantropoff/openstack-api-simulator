**Language / Язык:** [English](../getting-started.md) | [Русский](getting-started.md)

# Быстрый старт

Сквозная первая лабораторная сессия на Docker Compose. Для Kubernetes см.
[kubernetes.md](kubernetes.md).

## Требования

- Docker / Docker Compose
- Python 3.13+ (опционально, для smoke-скриптов на хосте)
- `curl` или OpenStack CLI / `openstacksdk`

## Выберите путь

| Путь | Когда |
|---|---|
| **1a. Опубликованный образ** | Лаборатория с Hub-образом (`docker-compose.release.yml`; нужен checkout репо для mount gateway/TLS) |
| **1b. Development checkout** | Будете менять код / пакеты |
| **Helm** | Установка в кластер — [kubernetes.md](kubernetes.md) |

## 1a. Опубликованный образ (Docker Hub)

Нужен **git checkout** этого репозитория: Compose монтирует
`./docker/gateway` и `./docker/tls` в nginx gateway. Контейнер симулятора
берётся с Docker Hub (локальная сборка приложения не нужна).

```bash
git clone https://github.com/inecs/openstack-api-simulator.git
cd openstack-api-simulator
docker compose -f docker-compose.release.yml up -d --wait
# или: make release-up
```

Образ: [`inecs/openstack-api-simulator`](https://hub.docker.com/r/inecs/openstack-api-simulator).
Тег при необходимости: `IMAGE_TAG=0.1.0`.

## 1b. Development checkout

```bash
cp .env.example .env
docker compose up -d --build --wait
```

## 2. Дождитесь готовности

```bash
curl -sf http://127.0.0.1:5000/health/ready
```

## 3. Загрузите seed-профиль

Minimal seed выполняется при первом старте. Опционально — полное синтетическое облако:

```bash
make seed-demo
# или
docker compose exec simulator python -m app.openstack.seed_cli --profile demo
```

Профили: [seed-profiles.md](seed-profiles.md).

## 4. Аутентификация (Keystone)

```bash
export OS_AUTH_URL=http://127.0.0.1:5000/v3
TOKEN=$(curl -si -X POST "$OS_AUTH_URL/auth/tokens" \
  -H 'Content-Type: application/json' \
  -d '{
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
  }' | awk -F': ' 'tolower($1)=="x-subject-token"{print $2}' | tr -d '\r')
echo "token=$TOKEN"
```

## 5. Вызовы Nova / Neutron

```bash
curl -sH "X-Auth-Token: $TOKEN" http://127.0.0.1:8774/v2.1/servers/detail | head -c 400
curl -sH "X-Auth-Token: $TOKEN" http://127.0.0.1:9696/v2.0/networks
```

## 6. Откройте Web UI

[http://localhost:5000/](http://localhost:5000/) — консоль, Environment drawer
(серия OpenStack pack + microversions), Data drawer (загрузка/выгрузка demo cloud).

## 7. Smoke / conformance

```bash
make smoke
python3 examples/python/openstack_smoke.py
python3 examples/python/openstack_conformance.py
```

## Готово, когда…

- `/health/ready` возвращает 200
- Keystone выдаёт `X-Subject-Token`
- списки Nova/Neutron содержат seed-ресурсы
- (опционально) demo cloud показывает ~1000 серверов

## Дальше

- [Порты](ports.md) — полная матрица портов сервисов
- [Покрытие API](api_coverage.md) — операции пакетов по сериям
- [Клиенты](clients.md) — openstacksdk / CLI
- [Kubernetes / Helm](kubernetes.md)
- [Hypervisor-lab](hypervisor-lab.md) — Pulumi-покрытие API (все ops × серии)
- [Эксплуатация](operations.md)
