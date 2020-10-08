#!/usr/bin/env bash
(
  cd ./py-deploy || exit 1
  CUSTOM_COMPILE_COMMAND="./compile-requirements" pip-compile --output-file=requirements.txt setup.py constraints.in "${@}"
)
CUSTOM_COMPILE_COMMAND="./compile-requirements" pip-compile --allow-unsafe dev-requirements.in "${@}"
