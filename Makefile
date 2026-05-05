PYTHON ?= .venv/bin/python
COMPOSE ?= docker compose

.PHONY: up down restart logs ps build smoke test

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) down
	$(COMPOSE) up --build -d

logs:
	$(COMPOSE) logs -f web worker-ai worker-glpi redis

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

smoke:
	$(PYTHON) scripts/docker_smoke_test.py

test:
	$(PYTHON) -m pytest -q
