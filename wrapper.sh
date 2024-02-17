#!/bin/bash
set -euo pipefail

COMPONENT=$1
echo $(date --iso-8601=second) -- Starting $COMPONENT

PYTHON=${HOME}/venv-tf-python39/bin/python
CODE=${HOME}/libera

export PYTHONIOENCODING="utf8:backslashreplace"
export PATH=${PATH}:${CODE}/bin

exec ${PYTHON} ${CODE}/${COMPONENT}.py --logfile ${HOME}/${COMPONENT}.log
