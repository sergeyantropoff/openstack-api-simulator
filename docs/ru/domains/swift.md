**Language / Язык:** [English](../../domains/swift.md) | [Русский](swift.md)

# Swift (object storage)

Порт **8080** на **gateway** (внутренний simulator остаётся на 8080 за nginx).

## Stateful

Accounts/containers/objects в таблицах `os_swift_*`. Demo seed создаёт
контейнеры `images` / `backups` / `artifacts` с readme-объектом на проект.
