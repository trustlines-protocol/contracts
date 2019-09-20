VIRTUALENV ?= python3 -m venv

all:: compile

clean::
	rm -rf build/contracts.json .requirements-installed

.requirements-installed:
	@echo "===> Installing requirements in your local virtualenv"
	pip install -q -c constraints.txt -r requirements.txt
	@touch .requirements-installed

install-requirements:: .requirements-installed

compile:: install-requirements
	@echo "==> Compiling contracts"
	deploy-tools compile --optimize --evm-version constantinople
	cp -p build/contracts.json py-bin/

install0:: SETUPTOOLS_SCM_PRETEND_VERSION = $(shell python3 -c 'from setuptools_scm import get_version; print(get_version())')
install0:: compile
	@echo "==> Installing py-bin/py-deploy into your local virtualenv"
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(SETUPTOOLS_SCM_PRETEND_VERSION) pip install ./py-bin
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(SETUPTOOLS_SCM_PRETEND_VERSION) pip install $(PIP_DEPLOY_OPTIONS) ./py-deploy

dist:: compile
	cd py-bin; python setup.py sdist
	cd py-deploy; python setup.py sdist

install:: PIP_DEPLOY_OPTIONS = -q -e
install:: install-requirements install0

install-non-editable:: PIP_DEPLOY_OPTIONS = -q
install-non-editable:: install-requirements install0
