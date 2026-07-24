VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
FLAKE8  := $(VENV)/bin/flake8
MYPY    := $(VENV)/bin/mypy
PYTEST  := $(VENV)/bin/pytest

# Default map for `make run` / `make debug`; override: make run MAP=maps/hard/01_maze_nightmare.txt
MAP ?= maps/easy/01_linear_path.txt

MYPY_FLAGS        := --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
MYPY_STRICT_FLAGS := --strict

.PHONY: install run debug lint lint-strict test clean fclean re

install: $(VENV)/.installed  ## Create venv and install tooling

$(VENV)/.installed: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	touch $(VENV)/.installed

run:  ## Parse+validate a map: make run MAP=<path>
	$(PY) main.py $(MAP)

debug:  ## Same as run with verbose dump
	$(PY) main.py $(MAP) --debug

lint:  ## flake8 + mypy (subject-required flags)
	$(FLAKE8) .
	$(MYPY) . $(MYPY_FLAGS)

lint-strict:  ## mypy --strict (recommended)
	$(MYPY) . $(MYPY_STRICT_FLAGS)

test:  ## Run the unit tests
	$(PYTEST) -q

clean:  ## Remove caches and bytecode
	rm -rf .mypy_cache .pytest_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

fclean: clean  ## clean + remove the virtualenv
	rm -rf $(VENV)

re: fclean install  ## Full rebuild
