# First Python >= 3.10 found on PATH; used only to build the venv.
PYTHON  := $(shell for p in python3.13 python3.12 python3.11 python3.10 python3; do \
	command -v $$p >/dev/null 2>&1 && $$p -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null && { echo $$p; break; }; \
	done)

VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
FLAKE8  := $(VENV)/bin/flake8
MYPY    := $(VENV)/bin/mypy
PYTEST  := $(VENV)/bin/pytest

MYPY_FLAGS        := --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
MYPY_STRICT_FLAGS := --strict

.DEFAULT_GOAL := help
.PHONY: help install run debug lint lint-strict test clean fclean re

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  %-12s %s\n", $$1, $$2}'

install: $(VENV)/.installed

$(VENV)/.installed: requirements.txt
	@test -n "$(PYTHON)" \
		|| { echo "❌ no Python 3.10+ found on PATH (system python3 is $$(python3 -V 2>&1))" >&2; exit 1; }
	@$(PYTHON) -m venv $(VENV) && echo "✅ venv created with $$($(PYTHON) -V 2>&1)" \
		|| { echo "❌ venv creation failed" >&2; exit 1; }
	@$(PIP) install --upgrade pip >/dev/null 2>&1 && echo "✅ pip upgraded" \
		|| { echo "❌ pip upgrade failed (check network)" >&2; exit 1; }
	@grep -vE '^\s*#|^\s*$$' requirements.txt | while read -r tool; do \
		$(PIP) install "$$tool" >/dev/null 2>&1 && echo "✅ $$tool installed" \
			|| { echo "❌ $$tool install failed (check network / name)" >&2; exit 1; }; \
	done
	@touch $(VENV)/.installed

run: install  ## Solve a map, print run to stdout: make run MAP=<path>
	@test -n "$(MAP)" || { echo "❌ Usage: make run MAP=<path/to/map.txt>" >&2; exit 1; }
	@$(PY) main.py "$(MAP)"

debug: install  ## Run the main script under Python's debugger (pdb)
	@test -n "$(MAP)" || { echo "❌ Usage: make debug MAP=<path/to/map.txt>" >&2; exit 1; }
	$(PY) -m pdb main.py "$(MAP)"

lint: install
	$(FLAKE8) ./*.py
	$(MYPY) ./*.py $(MYPY_FLAGS)

lint-strict: install
	$(MYPY) ./*.py $(MYPY_STRICT_FLAGS)

test: install  ## Run the unit tests
	$(PYTEST) -q

clean:
	rm -rf .mypy_cache .pytest_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -maxdepth 1 -type f -name '*.html' ! -name 'viz_template.html' -delete
	rm -f result_*.txt

fclean: clean
	rm -rf $(VENV)

re: fclean install  ## Full rebuild
