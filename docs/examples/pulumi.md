**Language / Язык:** [English](pulumi.md) | [Русский](../ru/examples/pulumi.md)

# Pulumi (pulumi_openstack)

## Cookbook (single stack)

[`examples/pulumi/`](../../examples/pulumi/) — `pulumi_openstack` Instance,
Network, Subnet against the simulator.

```bash
make up && make seed-demo
cd examples/pulumi
pulumi stack init dev --secrets-provider passphrase
export PULUMI_CONFIG_PASSPHRASE=lab
pulumi up
pulumi destroy
```

## Coverage lab (`pulumi-tests`)

[`pulumi-tests/`](../../pulumi-tests/) runs `pulumi_openstack` coverage stacks for
every series, asserts non-empty exports, then HTTP-probes pack operations with
non-empty body checks.

```bash
make pulumi-tests
open pulumi-tests/reports/pulumi-report.html
```

See [hypervisor-lab.md](../hypervisor-lab.md).
