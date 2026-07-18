COMPOSE ?= docker compose
SERVICE_DEV := dev
SERVICE_SIM := simulator
PYTEST_OFFLINE := -m "not integration and not compatibility"

# Docker Hub release image (runtime target only — not the local bind-mount "dev" image).
DOCKERHUB_USER ?= inecs
IMAGE_NAME ?= openstack-api-simulator
VERSION ?= $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
DOCKER_IMAGE ?= $(DOCKERHUB_USER)/$(IMAGE_NAME)
PUSH_LATEST ?= 1

COMPOSE_RELEASE ?= $(COMPOSE) -f docker-compose.release.yml
HELM_CHART ?= ./helm/openstack-api-simulator

.PHONY: help install format lint typecheck test test-unit test-integration test-contract test-compatibility test-surface evidence coverage run dev up down restart logs docker-build docker-up docker-down docker-logs docker-restart db-up db-down db-migrate db-reset api-import api-diff seed seed-demo smoke clean ci ci-all shell release release-build release-up release-down release-seed helm-deps helm-template \
	test-pulumi-smoke test-pulumi pulumi-tests test-smoke-all-lab test-all-lab clean-test-resources

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Build runtime and development images
	@test -f .env || cp .env.example .env
	$(COMPOSE) build simulator $(SERVICE_DEV)

format: ## Format Python sources
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) ruff format .

lint: ## Run Ruff lint checks
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) ruff check .

typecheck: ## Run strict mypy checks
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) mypy

test: ## Run offline unit and contract tests
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) pytest $(PYTEST_OFFLINE)

test-unit: ## Run unit tests
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) pytest tests/unit

test-integration: ## Run tests that require PostgreSQL
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm $(SERVICE_DEV) pytest -m integration

test-contract: ## Run offline API contract tests
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) pytest -m contract

test-compatibility: ## Run OpenStack smoke against the Compose stack
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build --wait
	$(COMPOSE) run --rm --entrypoint python $(SERVICE_SIM) -m app.openstack.seed_cli --profile minimal
	python3 examples/python/openstack_smoke.py

test-surface: ## Probe every OpenStack pack operation (Yoga→Dalmatian)
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --wait
	$(COMPOSE) run --rm --no-deps --entrypoint python $(SERVICE_SIM) examples/python/openstack_surface_probe.py --host http://api-gateway:5000
	$(COMPOSE) run --rm --no-deps --entrypoint python $(SERVICE_SIM) -m pytest tests/openstack -q --tb=line

evidence: ## Regenerate per-major verified surface evidence ledgers
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) python -m app.evidence_gen

coverage: ## Run offline tests with coverage enforcement
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) pytest $(PYTEST_OFFLINE) --cov=app --cov-report=term-missing --cov-report=xml

run: ## Run the application in the foreground
	@test -f .env || cp .env.example .env
	$(COMPOSE) up --build

up: ## Start PostgreSQL, simulator, and TLS gateway
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build --wait

down: ## Stop local services
	$(COMPOSE) down

restart: ## Rebuild and restart the stack
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build --force-recreate --wait

logs: ## Follow logs from all services
	$(COMPOSE) logs -f

dev: ## Run the application with auto-reload in Docker
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d postgres migrate
	$(COMPOSE) up simulator

docker-build: ## Build runtime and development images
	$(MAKE) install

docker-up: up ## Alias for up

docker-restart: ## Rebuild and recreate simulator and TLS gateway only
	$(COMPOSE) up -d --build --force-recreate simulator tls-gateway

docker-down: down ## Alias for down

docker-logs: ## Follow simulator logs only
	$(COMPOSE) logs -f simulator

db-up: ## Start PostgreSQL only
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d postgres

db-down: ## Stop PostgreSQL
	$(COMPOSE) stop postgres

db-migrate: ## Apply database migrations
	@test -f .env || cp .env.example .env
	$(COMPOSE) run --rm migrate

db-reset: ## Recreate the local database volume
	$(COMPOSE) down -v
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm migrate

api-import: ## Import an API snapshot
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) openstack-api-contract import $(ARGS)

api-diff: ## Compare API snapshots
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) openstack-api-contract diff $(ARGS)

seed: ## Seed minimal OpenStack lab data
	@test -f .env || cp .env.example .env
	SEED_PROFILE="$${PROFILE:-minimal}" $(COMPOSE) run --rm --entrypoint python $(SERVICE_SIM) -m app.openstack.seed_cli --profile "$${PROFILE:-minimal}"

seed-demo: ## Seed full OpenStack demo cloud (~1000 servers)
	@test -f .env || cp .env.example .env
	$(COMPOSE) run --rm --entrypoint python $(SERVICE_SIM) -m app.openstack.seed_cli --profile demo

smoke: ## Keystone → multi-service OpenStack smoke
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --wait
	python3 examples/python/openstack_smoke.py

shell: ## Open an interactive shell in the development container
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) bash

clean: ## Remove generated local artifacts
	rm -rf .coverage coverage.xml htmlcov .mypy_cache .pytest_cache .ruff_cache

ci: ## Offline quality gate + full API surface probe (Postgres)
	$(COMPOSE) run --rm --no-deps $(SERVICE_DEV) sh -c '\
		ruff format --check . && \
		ruff check . && \
		mypy && \
		pytest $(PYTEST_OFFLINE) --cov=app --cov-report=term-missing --cov-report=xml'
	$(MAKE) test-surface

ci-all: ## Full CI: offline + surface + remaining integration + client compatibility
	$(MAKE) ci
	$(MAKE) test-integration
	$(MAKE) test-compatibility

release-build: ## Build the runtime image tagged for Docker Hub (no push)
	@test -n "$(VERSION)" || (echo "VERSION is empty; set VERSION=... or version in pyproject.toml" >&2; exit 1)
	@echo "Building $(DOCKER_IMAGE):$(VERSION) (target=runtime)"
	docker build \
		--target runtime \
		--build-arg APP_VERSION=$(VERSION) \
		-t $(DOCKER_IMAGE):$(VERSION) \
		$(if $(filter 1 true yes,$(PUSH_LATEST)),-t $(DOCKER_IMAGE):latest,) \
		.

release: release-build ## Build and push the runtime image to Docker Hub
	@echo "Pushing $(DOCKER_IMAGE):$(VERSION)"
	@docker push $(DOCKER_IMAGE):$(VERSION)
	@if [ "$(PUSH_LATEST)" = "1" ] || [ "$(PUSH_LATEST)" = "true" ] || [ "$(PUSH_LATEST)" = "yes" ]; then \
		echo "Pushing $(DOCKER_IMAGE):latest"; \
		docker push $(DOCKER_IMAGE):latest; \
	fi
	@echo "Released $(DOCKER_IMAGE):$(VERSION)$(if $(filter 1 true yes,$(PUSH_LATEST)), and $(DOCKER_IMAGE):latest,)"

release-up: ## Pull and start the published Hub stack (docker-compose.release.yml)
	IMAGE_TAG="$${IMAGE_TAG:-$(VERSION)}" DOCKER_IMAGE="$(DOCKER_IMAGE)" $(COMPOSE_RELEASE) pull
	IMAGE_TAG="$${IMAGE_TAG:-$(VERSION)}" DOCKER_IMAGE="$(DOCKER_IMAGE)" $(COMPOSE_RELEASE) up -d --wait

release-down: ## Stop the published Hub stack
	$(COMPOSE_RELEASE) down

release-seed: ## Seed the published Hub stack (PROFILE=minimal|demo)
	SEED_PROFILE="$${PROFILE:-minimal}" IMAGE_TAG="$${IMAGE_TAG:-$(VERSION)}" DOCKER_IMAGE="$(DOCKER_IMAGE)" \
		$(COMPOSE_RELEASE) run --rm --entrypoint python simulator -m app.openstack.seed_cli --profile "$${PROFILE:-minimal}"

helm-deps: ## No-op placeholder (chart has no OCI dependencies)
	@echo "Chart $(HELM_CHART) vendors PostgreSQL templates; no helm dependency update required."

helm-template: ## Render Helm manifests locally (requires helm)
	helm template os-sim $(HELM_CHART) \
		-f $(HELM_CHART)/values-ingress-example.yaml \
		--set certManager.email=docs@example.com \
		--set secret.ticketSigningKey=docs-only-signing-key

# --- API coverage lab (pulumi-tests/, Pulumi only) ---
test-pulumi-smoke: ## Pulumi API coverage smoke (all series, collections GET)
	$(MAKE) -C pulumi-tests test-pulumi-smoke

test-pulumi: ## Pulumi API coverage full (all series, lifecycle)
	$(MAKE) -C pulumi-tests test-pulumi

pulumi-tests: ## Run full pulumi-tests suite (alias)
	$(MAKE) -C pulumi-tests pulumi-tests

test-smoke-all-lab: ## Alias → test-pulumi-smoke
	$(MAKE) -C pulumi-tests test-pulumi-smoke

test-all-lab: ## Alias → test-pulumi
	$(MAKE) -C pulumi-tests test-pulumi

clean-test-resources: ## Reseed demo for lab suites
	$(MAKE) -C pulumi-tests clean-test-resources
