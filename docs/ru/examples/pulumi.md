**Language / Язык:** [English](../../examples/pulumi.md) | [Русский](pulumi.md)

# Pulumi (pulumi_openstack)

## Cookbook (один stack)

[`examples/pulumi/`](../../../examples/pulumi/) — `pulumi_openstack` Instance,
Network, Subnet.

```bash
make up && make seed-demo
cd examples/pulumi
pulumi stack init dev --secrets-provider passphrase
export PULUMI_CONFIG_PASSPHRASE=lab
pulumi up
pulumi destroy
```

## Лаборатория покрытия (`pulumi-tests`)

[`pulumi-tests/`](../../../pulumi-tests/) — стеки `pulumi_openstack` на каждую
серию, проверка непустых export'ов, затем HTTP-probe pack-операций с
непустыми телами.

```bash
make pulumi-tests
open pulumi-tests/reports/pulumi-report.html
```

См. [hypervisor-lab.md](../hypervisor-lab.md).
