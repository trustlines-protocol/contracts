all:: venv-populus compile

venv-populus:
	python3 -m venv venv-populus
	venv-populus/bin/pip install -U pip wheel
	venv-populus/bin/pip install -c constraints.txt populus

compile:: venv-populus
	venv-populus/bin/populus compile

clean::
	rm -rf venv-populus build/contracts.json
