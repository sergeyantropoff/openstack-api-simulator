**Language / Язык:** [English](python-openstacksdk.md) | [Русский](../ru/examples/python-openstacksdk.md)

# Python + openstacksdk

```python
import openstack

conn = openstack.connect(
    auth_url="http://127.0.0.1:5000/v3",
    project_name="demo",
    username="admin",
    password="secret",
    user_domain_name="Default",
    project_domain_name="Default",
)

for server in conn.compute.servers():
    print(server.name, server.status)
for network in conn.network.networks():
    print(network.name)
```

Ensure the service catalog ports are reachable (Compose gateway or Helm
port-forward). See [clients.md](../clients.md).
