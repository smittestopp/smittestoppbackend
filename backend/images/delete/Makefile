

.PHONY: clean clean-test clean-pyc

current_dir = $(shell pwd)

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
	python -m flake8 --max-line-length=88 corona_delete/tests/*.py

black:
	python -m black corona_delete/tests/*.py

isort:
	python -m isort -y corona_delete/tests/*.py
	

install-dev-deps:
	python -m pip install black isort flake8 pytest pytest-cov pytest-tornado testfixtures

check: lint black isort

start:
	python -m corona_delete.delete

source: 
	@echo "First make sure to create a virtual environment:"
	@echo "python -m virtualenv venv"
	@echo "python -m pip install -r requirements.txt"
	@echo "python -m pip install -r ../corona/requirements.txt"

	@echo ""
	@echo "Then run the following command:"
	@echo "source venv/bin/activate && set -a && source ../../secrets/dev/env-file && set +a"	
	@echo "export PYTHONPATH=$(current_dir)/../corona:$$PYTHONPATH"
	
test:
	python -m pytest --async-test-timeout 15 -vv --cov=corona_delete --capture=tee-sys --cov-report html