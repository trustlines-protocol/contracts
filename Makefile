VERSION=$(shell python3 -c 'from setuptools_scm import get_version; print(get_version())')
VIRTUALENV ?= python3 -m venv

all:: venv-populus compile

venv-populus:
	$(VIRTUALENV) venv-populus
	venv-populus/bin/pip install -U pip wheel
	venv-populus/bin/pip install -c constraints-populus.txt populus

compile:: venv-populus
	venv-populus/bin/populus compile
	cp -p build/contracts.json py-bin/

clean::
	rm -rf venv-populus build/contracts.json

install:: compile
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(VERSION) pip install ./py-bin
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(VERSION) pip install -e ./py-deploy

install-non-editable:: compile
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(VERSION) pip install ./py-bin
	/usr/bin/env SETUPTOOLS_SCM_PRETEND_VERSION=$(VERSION) pip install ./py-deploy
