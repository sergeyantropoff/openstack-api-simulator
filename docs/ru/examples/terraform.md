**Language / Язык:** [English](../../examples/terraform.md) | [Русский](terraform.md)

# Terraform (openstack provider)

## Cookbook (один stack)

[`examples/terraform/main.tf`](../../../examples/terraform/main.tf) —
**`terraform-provider-openstack/openstack`**.

```bash
make up && make seed-demo
cd examples/terraform
terraform init
terraform apply
terraform destroy
```

По умолчанию: `auth_url = http://127.0.0.1:5000/v3`, `admin` / `secret`, проект `demo`.

Интеграционное покрытие API — в [`pulumi-tests/`](../../../pulumi-tests/)
(Pulumi / `pulumi_openstack`). См. [hypervisor-lab.md](../hypervisor-lab.md).
