

.PHONY: clean clean-test clean-pyc docker/build docker/test docker/build-test


clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

clean: clean-pyc clean-test

lint:
	python -m flake8 --max-line-length=88 corona_backend

black:
	python -m black corona_backend

isort:
	python -m isort -y -rc corona_backend/

install-dev-deps:
	python -m pip install black isort flake8 pytest pytest-cov pytest-asyncio pytest-tornado testfixtures docker

check: isort black lint

source:
	@echo "First make sure to create a virtual environment:"
	@echo "python -m virtualenv venv"
	@echo "python -m pip install -r requirements.txt"
	@echo ""
	@echo "Then run the following command:"
	@echo "source venv/bin/activate && set -a && source ../../secrets/dev/env-file && set +a"

start:
	python -m corona_backend

PYTEST_MOD ?= corona_backend
PYTEST_ARGS ?= -vv

test:
	ASYNC_TEST_TIMEOUT=10 \
	PROVISIONING_TIMEOUT=1 \
	python -m pytest \
		$(PYTEST_ARGS) \
		--cov=corona_backend \
		--cov-report html \
		--pyargs $(PYTEST_MOD) \
