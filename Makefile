VIRTUALENV ?= python3 -m venv

all:: venv-populus compile

venv-populus:
	@echo "==> Creating virtualenv for populus"
	$(VIRTUALENV) venv-populus
	venv-populus/bin/pip install -q -U pip wheel
	venv-populus/bin/pip install -q -c constraints-populus.txt populus

compile:: venv-populus
	@echo "==> Compiling contracts"
	venv-populus/bin/populus compile
	cp -p build/contracts.json py-bin/

clean::
	rm -rf venv-populus build/contracts.json .requirements-installed

.requirements-installed:
	@echo "===> Installing requirements in your local virtualenv"
	pip install -q -c constraints.txt -r requirements.txt
	@touch .requirements-installed

install-requirements:: .requirements-installed

install0:: SETUPTOOLS_SCM_PRETEND_VERSION = $(shell python3 -c 'from setuptools_scm import get_version; print(get_version())')
install0:: compile
	@echo "==> Installing py-bin/py-deploy into your local virtualenv"
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(SETUPTOOLS_SCM_PRETEND_VERSION) pip install ./py-bin
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(SETUPTOOLS_SCM_PRETEND_VERSION) pip install $(PIP_DEPLOY_OPTIONS) ./py-deploy


install:: PIP_DEPLOY_OPTIONS = -q -e
install:: install-requirements install0

install-non-editable:: PIP_DEPLOY_OPTIONS = -q
install-non-editable:: install-requirements install0
