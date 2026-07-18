# Pulumi OpenStack coverage lab (pulumi_openstack + HTTP nonempty checks).
COMPOSE ?= docker compose
COMPOSE_FILE ?= docker-compose.yml
COMPOSE_CMD = $(COMPOSE) -f $(COMPOSE_FILE)
PROFILE = --profile test

.PHONY: help up down build seed test-pulumi-smoke test-pulumi pulumi-tests clean-test-resources report

help: ## Show targets
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-26s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start simulator + gateway + seed
	$(COMPOSE_CMD) up -d --build postgres
	$(COMPOSE_CMD) up --build migrate
	$(COMPOSE_CMD) up -d --build simulator api-gateway
	$(COMPOSE_CMD) up --build seed

down: ## Stop lab stack
	$(COMPOSE_CMD) --profile test down -v

build: ## Build Pulumi runner image
	$(COMPOSE_CMD) $(PROFILE) build pulumi-runner

seed: ## Re-run demo seed
	$(COMPOSE_CMD) up --build seed

test-pulumi-smoke: up ## Fast: pulumi_openstack + collection GET nonempty × all series
	mkdir -p reports
	$(COMPOSE_CMD) $(PROFILE) run --rm -e TEST_SMOKE=1 pulumi-runner \
		python3 /suite/pulumi/run_suite.py

test-pulumi: up ## Full: pulumi_openstack + lifecycle HTTP nonempty × all series
	mkdir -p reports
	$(COMPOSE_CMD) $(PROFILE) run --rm pulumi-runner \
		python3 /suite/pulumi/run_suite.py

pulumi-tests: test-pulumi ## Alias for full suite

report: ## Rebuild HTML from series-*.json on host
	PYTHONPATH=pulumi python3 -c "from pathlib import Path; import json; from _lib.report_html import write_html, load_series_files; \
d=Path('reports'); reps=load_series_files(d); s=json.loads((d/'summary.json').read_text()) if (d/'summary.json').exists() else {}; \
print(write_html(d, s, reps))"

clean-test-resources: ## Best-effort cleanup via seed reload
	$(COMPOSE_CMD) up --build seed
