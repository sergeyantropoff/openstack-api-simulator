**Language / Язык:** [English](README.md) | [Русский](ru/README.md)

# Documentation

Guides for the OpenStack API Simulator laboratory. Switch language with the
header on each page. Russian mirrors live under [`ru/`](ru/README.md).

| Guide | Topic |
|---|---|
| [Getting started](getting-started.md) | First lab session (Compose) |
| [Kubernetes / Helm](kubernetes.md) | Cluster install, Ingress, cert-manager |
| [Configuration](configuration.md) | Env vars, Compose, Helm knobs |
| [Authentication](authentication.md) | Keystone tokens & seeded users |
| [Ports](ports.md) | Real OpenStack API ports (1:1 host publish) |
| [API surface](api-surface.md) | Specialized vs schema packs |
| [API versions](api-versions.md) | Yoga → Dalmatian series |
| [API coverage](api_coverage.md) | Generated operation counts |
| [Seed profiles](seed-profiles.md) | `minimal` / `demo` |
| [Clients](clients.md) | SDK / CLI |
| [Web UI](web-ui.md) | Console drawers |
| [Operations](operations.md) | Day-2, release, reseed, **testing** |
| [Architecture](architecture.md) | Components & request path |
| [Security](security.md) | Lab threat model |
| [Observability](observability.md) | Health & logs |
| [Troubleshooting](troubleshooting.md) | Common failures |
| [FAQ](faq.md) | Short Q&A |
| [Domains](domains/README.md) | Per-service notes |
| [Examples](examples/overview.md) | Client cookbooks |
| [Hypervisor-lab](hypervisor-lab.md) | Pulumi API coverage (all ops × series) |

Runnable cookbooks: [`examples/`](../examples/README.md).
Integration suites: [`pulumi-tests/`](../pulumi-tests/README.md).

Back to [README](../README.md).
