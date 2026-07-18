#!/usr/bin/env bash
# Run Python + Ansible + Terraform + Pulumi cookbooks against local simulator.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Prefer CLT/system python (user site-packages) over Homebrew for cookbooks.
export PATH="${HOME}/.local/bin:${HOME}/Library/Python/3.9/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:${PATH}"
# Local lab must not go through IDE/sandbox HTTP proxies (breaks multi-port discovery).
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY="*"
export no_proxy="*"
export OS_AUTH_URL="${OS_AUTH_URL:-http://127.0.0.1:5000/v3}"
export OS_USERNAME="${OS_USERNAME:-admin}"
export OS_PASSWORD="${OS_PASSWORD:-secret}"
export OS_PROJECT_NAME="${OS_PROJECT_NAME:-demo}"
export OS_USER_DOMAIN_NAME="${OS_USER_DOMAIN_NAME:-Default}"
export OS_PROJECT_DOMAIN_NAME="${OS_PROJECT_DOMAIN_NAME:-Default}"
export OS_IDENTITY_API_VERSION=3
export OS_REGION_NAME="${OS_REGION_NAME:-RegionOne}"
PYTHON="${PYTHON:-/usr/bin/python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python3
fi

cd "$ROOT"
echo "== health =="
curl -sf "$OS_AUTH_URL/../health/ready" >/dev/null || curl -sf "http://127.0.0.1:5000/health/ready"

echo "== ensure demo seed (networks/images) =="
docker compose exec -T simulator python -m app.openstack.seed_cli --profile demo >/dev/null

echo "== 1) Python openstacksdk =="
"$PYTHON" -m pip install -q --user openstacksdk >/dev/null 2>&1 || true
"$PYTHON" examples/python/openstacksdk_cookbook.py

echo "== 2) Ansible =="
ansible-playbook -i examples/ansible/inventory.ini examples/ansible/playbook.yml

if command -v terraform >/dev/null 2>&1; then
  echo "== 3) Terraform =="
  cd examples/terraform
  terraform init -input=false
  terraform apply -auto-approve -input=false
  terraform destroy -auto-approve -input=false
  cd "$ROOT"
else
  echo "== 3) Terraform SKIPPED (terraform not installed) =="
fi

if command -v pulumi >/dev/null 2>&1; then
  echo "== 4) Pulumi =="
  cd examples/pulumi
  "$PYTHON" -m pip install -q --user -r requirements.txt >/dev/null 2>&1 || "$PYTHON" -m pip install -q -r requirements.txt
  pulumi stack select dev --create 2>/dev/null || true
  pulumi config set openstack:authUrl "$OS_AUTH_URL"
  pulumi config set openstack:userName "$OS_USERNAME"
  pulumi config set --secret openstack:password "$OS_PASSWORD"
  pulumi config set openstack:tenantName "$OS_PROJECT_NAME"
  pulumi config set openstack:domainName "$OS_USER_DOMAIN_NAME"
  pulumi config set openstack:region "$OS_REGION_NAME"
  # Pulumi Python programs should use the same interpreter
  export PULUMI_PYTHON_CMD="$PYTHON"
  pulumi up --yes
  pulumi destroy --yes
  cd "$ROOT"
else
  echo "== 4) Pulumi SKIPPED (pulumi CLI not installed; SDK cookbook covered by Python) =="
  echo "    Install: brew install pulumi/tap/pulumi   then re-run this script"
fi

echo "IAC_STACK_DONE"
