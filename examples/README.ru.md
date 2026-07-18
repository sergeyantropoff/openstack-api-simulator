**Language / Язык:** [English](README.md) | [Русский](README.ru.md)

# Исполняемые примеры OpenStack

Сопровождающий код к [docs/ru/clients.md](../docs/ru/clients.md) и
[docs/ru/examples/overview.md](../docs/ru/examples/overview.md).

Этот репозиторий — **OpenStack** API lab (не VMware). Используйте ресурсы
`openstack_*` Terraform / `pulumi_openstack` — не `vsphere_virtual_machine`.

## Требования

```bash
make up
make seed-demo   # networks, images (cirros), flavors, …
```

Учётные данные по умолчанию: `admin` / `secret`, проект `demo`, домен `Default`.  
Auth URL: `http://127.0.0.1:5000/v3`.

Для локальных cookbook'ов отключите HTTP-прокси (IDE-песочницы часто
подставляют его и ломают multi-port discovery Keystone/Glance/Nova):

```bash
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY='*'
```

## Полный стек (Python + Ansible + Terraform + Pulumi)

```bash
bash examples/run_iac_stack.sh
```

| Шаг | Путь | Что делает |
|---|---|---|
| Python | `python/openstacksdk_cookbook.py` | net/subnet + server + volume через openstacksdk |
| Ansible | `ansible/playbook.yml` | токен Keystone + Nova/Neutron/Glance через `uri` |
| Terraform | `terraform/main.tf` | `openstack_compute_instance_v2` + volume attach |
| Pulumi | `pulumi/` | `pulumi_openstack` Instance + Network/Subnet |

## Другие probe'ы

| Путь | Назначение |
|---|---|
| `python/openstack_smoke.py` | Multi-port GET smoke |
| `python/openstack_conformance.py` | Write-path + UI contracts |
| `python/openstack_surface_probe.py` | Полный lifecycle-probe пакета |
