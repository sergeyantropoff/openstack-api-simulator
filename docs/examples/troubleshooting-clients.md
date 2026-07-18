**Language / Язык:** [English](troubleshooting-clients.md) | [Русский](../ru/examples/troubleshooting-clients.md)

# Client troubleshooting

## Catalog points at unreachable hosts

The seed catalog uses `host.docker.internal` or compose service hostnames in
some setups. Override endpoints or use the gateway host you actually expose
(`127.0.0.1` with port-forward).

## SSL errors against Ingress

Lab staging issuers are untrusted — use `curl -k` / `OS_INSECURE=true` only in labs.

## Empty server list

Wrong project scope, or demo not loaded. Check:

```bash
openstack project list
make seed-demo
```

## Microversion rejected

Lower the requested compute microversion or apply an earlier series in the API catalog.
