**Language / Язык:** [English](../web-ui.md) | [Русский](web-ui.md)

# Web UI

Консоль обслуживается с Keystone/UI порта (**5000** на gateway).

| URL | Назначение |
|---|---|
| `/` или `/console` | Интерактивная консоль |
| `/docs` | OpenAPI (simulator) |
| `/ui/api/…` | UI JSON APIs |

![Главный экран консоли](../images/web-ui/console-main.png)

## Endpoints drawer

Обзор поверхности пака по сервисам (например Adjutant). У каждого path —
поддерживаемые HTTP-методы.

![Endpoints drawer](../images/web-ui/endpoints.png)

## Отправка запросов

Выберите verb + path и нажмите **Send**. Успешные ответы попадают в
**RESPONSE**.

![Запрос и ответ](../images/web-ui/request-response.png)

### Request parameters

Для `POST` / `PUT` / `PATCH` в **Request parameters** показаны поля схемы
(dotted-имена для вложенных OpenStack envelope), типы, optional и примеры.
JSON Request body собирается из этих полей.

![Request parameters](../images/web-ui/request-parameters.png)

## Authentication drawer

Вход через лабораторный Keystone (`admin` / `secret`, проекты вроде `admin`
или `demo`). Можно вставить готовый `X-Auth-Token`.

![Authentication drawer](../images/web-ui/authentication.png)

## Environment drawer

- Runtime / catalog / активная **microversion**, плюс живой инвентарь облака
  (servers, nets, volumes…)

![Environment drawer](../images/web-ui/environment.png)

## API catalog drawer

- Выбор карточки серии (`os · yoga` …), microversion в карточке, затем
  **Apply as runtime** (выбор сохраняется после перезагрузки)

![API catalog drawer](../images/web-ui/api-catalog.png)

## Data drawer

- **Load demo cloud** — кластеры small / large / big
- **Reset to minimal** — минимальный lab seed

![Data drawer](../images/web-ui/data.png)

## History drawer

Недавние вызовы консоли: method, URL и status.

![History drawer](../images/web-ui/history.png)

## Help · Compatibility

Покрытие поверхности пака для активной серии (declared / implemented,
сервисы, смесь verb).

![Help compatibility](../images/web-ui/help-compatibility.png)

## Брендинг

OpenStack red `#ED1C24`, console wordmark. Темы следуют общему chrome консоли
(light/dark).

## Health

- `/health/live` — процесс работает
- `/health/ready` — миграции применены + БД доступна
