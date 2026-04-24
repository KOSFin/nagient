PYTHON ?= python3
PYTHONPATH_VALUE ?= src
PYCACHE_PREFIX ?= .pycache

.PHONY: check-python install-dev lint test smoke coverage build docker-build manifest

check-python:
	@$(PYTHON) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python 3.11+ is required.')"

install-dev: check-python
	$(PYTHON) -m pip install -e .[dev]

lint: check-python
	PYTHONPATH=$(PYTHONPATH_VALUE) $(PYTHON) -m ruff check src tests scripts/release
	PYTHONPATH=$(PYTHONPATH_VALUE) $(PYTHON) -m mypy src

test: check-python
	PYTHONPATH=$(PYTHONPATH_VALUE) $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

smoke: check-python
	PYTHONPATH=$(PYTHONPATH_VALUE) PYTHONPYCACHEPREFIX=$(PYCACHE_PREFIX) $(PYTHON) -m compileall src
	PYTHONPATH=$(PYTHONPATH_VALUE) $(PYTHON) -m unittest discover -s tests/smoke -p 'test_*.py' -v

coverage: check-python
	PYTHONPATH=$(PYTHONPATH_VALUE) $(PYTHON) -m coverage run -m unittest discover -s tests -p 'test_*.py'
	PYTHONPATH=$(PYTHONPATH_VALUE) $(PYTHON) -m coverage report

build: check-python
	$(PYTHON) -m build

docker-build:
	docker build -t nagient:local .

manifest: check-python
	PYTHONPATH=$(PYTHONPATH_VALUE) $(PYTHON) scripts/release/build_release_manifest.py \
		--version 0.1.0 \
		--channel stable \
		--base-url / \
		--docker-image nagient:0.1.0 \
		--published-at 2026-04-24T00:00:00Z \
		--output metadata/update-center/manifests/0.1.0.json
