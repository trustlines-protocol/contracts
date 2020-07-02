VIRTUAL_ENV ?= $(shell pwd)/venv

all:: compile

clean::
	rm -rf build/contracts.json .requirements-installed

lint: setup-venv install-requirements
	$(VIRTUAL_ENV)/bin/flake8 tests py-deploy
	$(VIRTUAL_ENV)/bin/black --check tests py-deploy
	$(VIRTUAL_ENV)/bin/mypy --ignore-missing-imports tests py-deploy

test:: setup-venv install
	$(VIRTUAL_ENV)/bin/pytest tests

.requirements-installed: setup-venv dev-requirements.txt
	@echo "===> Installing requirements in your local virtualenv"
	$(VIRTUAL_ENV)/bin/pip install -q -r dev-requirements.txt
	@echo "This file controls for make if the requirements in your virtual env are up to date" > $@

install-requirements:: .requirements-installed

compile:: setup-venv install-requirements
	@echo "==> Compiling contracts"
	$(VIRTUAL_ENV)/bin/deploy-tools compile --optimize
	cp -p build/contracts.json py-bin/

install0:: SETUPTOOLS_SCM_PRETEND_VERSION = $(shell python3 -c 'from setuptools_scm import get_version; print(get_version())')
install0:: setup-venv compile
	@echo "==> Installing py-bin/py-deploy into your local virtualenv"
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(SETUPTOOLS_SCM_PRETEND_VERSION) $(VIRTUAL_ENV)/bin/pip install ./py-bin
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(SETUPTOOLS_SCM_PRETEND_VERSION) $(VIRTUAL_ENV)/bin/pip install $(PIP_DEPLOY_OPTIONS) ./py-deploy

dist:: compile
	cd py-bin; python setup.py sdist
	cd py-deploy; python setup.py sdist

install:: PIP_DEPLOY_OPTIONS = -q -e
install:: setup-venv install-requirements install0

install-non-editable:: PIP_DEPLOY_OPTIONS = -q
install-non-editable:: setup-venv install-requirements install0

$(VIRTUAL_ENV):
	@echo "==> Creating virtualenv in $(VIRTUAL_ENV)"
	python3 -m venv $@

setup-venv: $(VIRTUAL_ENV)
	@echo "==> Using virtualenv in $(VIRTUAL_ENV)"

.PHONY: setup-venv
