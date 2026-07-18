**Language / Язык:** [English](../api-surface.md) | [Русский](api-surface.md)

# Поверхность API

## Surface-complete пакеты

Каждый пакет серии OpenStack перечисляет операции **method + path**. При старте
каждая уникальная пара `(method, path)` регистрируется как отдельный маршрут FastAPI
(`os-contract:…`), в стиле Proxmox. Stateful-обработчики из специализированных
модулей ищутся через `HandlerRegistry`; всё остальное уходит в schema-движок
(лабораторный JSON `os_api_objects`).

| Series | Services | Operations (approx.) |
|---|---|---|
| Yoga | 28 | ~1060 |
| Antelope | 28 | ~1108 |
| Caracal | 28 | ~1196 |
| Dalmatian | 28 | ~1357 |

Авторитетные числа: [api_coverage.md](api_coverage.md).

## Handlers vs schema fallback

| Слой | Сервисы / ресурсы |
|---|---|
| **Специализированные handlers** | Keystone tokens/catalog, Nova servers/flavors/keypairs/…, Neutron nets/ports/…, Glance images, Cinder volumes, Heat stacks, Swift, Ironic nodes, Octavia LBs, Placement RPs |
| **Schema fallback** | Остальные коллекции пакета (Barbican, Manila, Designate, Magnum, …), включая вложенные пути |

## Microversions

Заголовки вроде `OpenStack-API-Version: compute 2.79` и
`X-OpenStack-Nova-API-Version` принимаются и фильтруются по метаданным пакета.
Переопределения можно задать в Web UI Environment drawer.

## Actions

Nova-style `POST /servers/{id}/action` и аналогичные ops пакета `kind=action`
обрабатываются schema/action-путём (обновление power state для типичных actions).

## Ошибки

Ошибки в форме OpenStack (`OpenStackError`) с `code`, `title`, `message`.
Неизвестные маршруты, отсутствующие в активном contract-пакете, возвращают
стандартный FastAPI `404`.
