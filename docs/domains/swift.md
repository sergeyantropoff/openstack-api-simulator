**Language / Язык:** [English](swift.md) | [Русский](../ru/domains/swift.md)

# Swift (object storage)

Port **8080** on the **gateway** (internal simulator remains on 8080 behind nginx).

## Stateful

Accounts/containers/objects in `os_swift_*` tables. Demo seed creates
`images` / `backups` / `artifacts` containers with a readme object per project.
