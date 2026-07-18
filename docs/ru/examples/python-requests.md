**Language / Язык:** [English](../../examples/python-requests.md) | [Русский](python-requests.md)

# Python + requests

Минимальный пример password-auth и списка серверов Nova:

```python
import requests

AUTH = "http://127.0.0.1:5000/v3/auth/tokens"
r = requests.post(
    AUTH,
    json={
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": "admin",
                        "domain": {"name": "Default"},
                        "password": "secret",
                    }
                },
            },
            "scope": {
                "project": {"name": "demo", "domain": {"name": "Default"}}
            },
        }
    },
)
r.raise_for_status()
token = r.headers["X-Subject-Token"]
headers = {"X-Auth-Token": token}

servers = requests.get("http://127.0.0.1:8774/v2.1/servers", headers=headers)
print(servers.status_code, len(servers.json().get("servers", [])))
```
