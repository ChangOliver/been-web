.PHONY: dev api web install test lint build

NODE_NPM ?= /opt/homebrew/opt/node@20/bin/npm

install:
	/opt/homebrew/bin/python3.12 -m venv .venv
	.venv/bin/pip install -e 'apps/api[dev]'
	$(NODE_NPM) --prefix apps/web install

api:
	.venv/bin/uvicorn app.main:app --app-dir apps/api --reload --reload-dir apps/api --host 127.0.0.1 --port 8000

web:
	@if [ ! -x apps/web/node_modules/.bin/vite ]; then echo "Installing frontend dependencies..."; $(NODE_NPM) --prefix apps/web install; fi
	$(NODE_NPM) --prefix apps/web run dev

dev:
	@trap 'kill 0' INT TERM EXIT; $(MAKE) api & $(MAKE) web & wait

test:
	PYTHONPATH=apps/api .venv/bin/pytest apps/api/tests
	$(NODE_NPM) --prefix apps/web run test -- --run

lint:
	.venv/bin/ruff check apps/api
	$(NODE_NPM) --prefix apps/web run lint

build:
	$(NODE_NPM) --prefix apps/web run build
