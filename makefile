

SHELL = /bin/bash

.PHONY: help test test_fails trouble clean help_venv check_env reqs pypi

PROJECT=ox_task

PYTEST_EXTRA_FLAGS ?= ""


.EXPORT_ALL_VARIABLES:

# The stuff below implements an auto help feature
define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([.a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

help:   ## Show help for avaiable targets
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

test:   ## Run tests
	py.test -s -vvv --doctest-modules --doctest-glob='*.md' \
            ${PYTEST_EXTRA_FLAGS} .

cov:	## Run tests with code coverage
	PYTEST_EXTRA_FLAGS="$${PYTEST_EXTRA_FLAGS} --cov=src/ox_task \
            --cov-report term-missing" ${MAKE} test


pypi: README.rst
	fixme && exit 1
	rm -f dist/*
	python3 setup.py sdist
	twine upload --verbose -r pypi dist/*

README.rst: README.org  ## Auto generate README.rst from README.org
	pandoc --from=org --to=rst --output=README.rst README.org

