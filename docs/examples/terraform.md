**Language / Язык:** [English](terraform.md) | [Русский](../ru/examples/terraform.md)

# Terraform (openstack provider)

## Cookbook (single stack)

[`examples/terraform/main.tf`](../../examples/terraform/main.tf) uses
**`terraform-provider-openstack/openstack`** (`openstack_compute_instance_v2`,
network, volume attach) against the local gateway ports.

```bash
make up && make seed-demo
cd examples/terraform
terraform init
terraform apply
terraform destroy
```

Defaults: `auth_url = http://127.0.0.1:5000/v3`, user `admin`, project `demo`,
`insecure = true` (lab HTTP gateway).

API coverage integration suites now live under [`pulumi-tests/`](../../pulumi-tests/)
(Pulumi / `pulumi_openstack`). See [hypervisor-lab.md](../hypervisor-lab.md).
