VIRTUALENV ?= python3 -m venv

all:: compile

clean::
	rm -rf build/contracts.json .requirements-installed

lint: install-requirements
	flake8 tests py-deploy
	black --check tests py-deploy
	mypy --ignore-missing-imports tests py-deploy

test:: install
	pytest tests

.requirements-installed: dev-requirements.txt
	@echo "===> Installing requirements in your local virtualenv"
	pip install -q -r dev-requirements.txt --disable-pip-version-check
	pip install -q -r py-deploy/requirements.txt --disable-pip-version-check
	@echo "This file controls for make if the requirements in your virtual env are up to date" > $@

install-requirements:: .requirements-installed

compile:: install-requirements
	@echo "==> Compiling contracts"
	deploy-tools compile --optimize
	cp -p build/contracts.json py-bin/tlbin
	python py-bin/scripts/merge_abis.py py-bin/tlbin/legacy_currency_networks.json py-bin/tlbin/contracts.json py-bin/tlbin/merged_abis.json

install0:: SETUPTOOLS_SCM_PRETEND_VERSION = $(shell python3 -c 'from setuptools_scm import get_version; print(get_version())')
install0:: compile
	@echo "==> Installing py-bin/py-deploy into your local virtualenv"
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(SETUPTOOLS_SCM_PRETEND_VERSION) pip install $(PIP_INSTALL_OPTIONS) ./py-bin
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(SETUPTOOLS_SCM_PRETEND_VERSION) pip install $(PIP_INSTALL_OPTIONS) ./py-deploy

dist:: compile
	cd py-bin; python setup.py sdist
	cd py-deploy; python setup.py sdist

install:: PIP_INSTALL_OPTIONS = -q -e
install:: install-requirements install0

install-non-editable:: PIP_INSTALL_OPTIONS = -q
install-non-editable:: install-requirements install0
