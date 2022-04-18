#!/bin/bash
set -euo pipefail

COMPONENT=$1
echo $(date) -- Starting $COMPONENT

PYTHON=${HOME}/venv-tf-python39/bin/python
CODE=${HOME}/libera

export PYTHONIOENCODING="utf8:backslashreplace"
export PATH=${PATH}:${CODE}/bin

${PYTHON} ${CODE}/${COMPONENT}.py --logfile ${HOME}/${COMPONENT}.log

