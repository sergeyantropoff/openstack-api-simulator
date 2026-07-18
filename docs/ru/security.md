**Language / Язык:** [English](../security.md) | [Русский](security.md)

# Безопасность

Этот проект — **лабораторный симулятор**, а не production OpenStack cloud.

## Граница доверия

- Пароли по умолчанию (`secret`) намеренно простые для лабораторий.
- `TICKET_SIGNING_KEY` / `secret.ticketSigningKey` нужно ротировать перед любым
  общим или internet-facing развёртыванием.
- Пароли bundled Postgres в values/compose — лабораторные defaults.

## Сетевая экспозиция

| Surface | Риск |
|---|---|
| Compose ports on `0.0.0.0` | Вся поверхность API доступна на хосте |
| Helm Ingress | Публичный HTTPS к Keystone/UI; другие OS-порты требуют явной экспозиции |
| Read-only root FS (Helm) | Снижает write surface контейнера |

## TLS

- Compose: опциональный nginx TLS на `:443` с lab cert в `docker/tls/`
- Helm: terminate TLS на Ingress + cert-manager (рекомендуется)

## Что не реализовано

- Реальная federation Keystone / семантика ротации Fernet keys
- Паритет правил oslo.policy
- Multi-tenant isolation beyond project_id filters в handlers

Считайте все данные одноразовыми lab fixtures.
