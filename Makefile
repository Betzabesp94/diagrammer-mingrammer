SHELL := /bin/bash

VENV := .venv
PY   := $(VENV)/bin/python
SKILL := .claude/skills/diagrams-architect
PIP  := $(VENV)/bin/pip
FMT  ?= png

.PHONY: help install check render all clean diagram validate test evals golden

help:
	@echo "targets disponibles:"
	@echo "  make install                        crea el venv e instala las dependencias"
	@echo "  make check                          verifica python, graphviz y diagrams"
	@echo "  make render FILE=ejemplo_aws.py     genera output/ejemplo_aws.png"
	@echo "  make render FILE=ejemplo_aws.py FMT=svg"
	@echo "  make all                            renderiza todos los .py de diagrams_src/ y diagrams_ref/"
	@echo "  make clean                          vacía output/"
	@echo "  make diagram IN=diagrams_src/x.diag valida, genera el .py, renderiza y deja output/x.report.json"
	@echo "  make validate FILE=diagrams_src/x.py [IR=x.ir.json]   valida un .py (estricto si lo generó la skill)"
	@echo "  make test                           pruebas de la skill (unittest)"
	@echo "  make evals                          evals de la skill verificables por script"
	@echo "  make golden                         regenera tests/golden (solo si cambió el formato del generador)"

install:
	python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@$(MAKE) --no-print-directory check

check:
	@./render.sh --check

render:
	@if [ -z "$(FILE)" ]; then \
		echo "uso: make render FILE=ejemplo_aws.py [FMT=svg]"; exit 1; \
	fi
	@FORMAT=$(FMT) ./render.sh $(FILE)

all:
	@shopt -s nullglob; \
	for f in diagrams_ref/[!_]*.py diagrams_src/[!_]*.py; do FORMAT=$(FMT) ./render.sh "$$f"; done

clean:
	@find output -mindepth 1 ! -name .gitkeep -delete
	@echo "output/ vacío"

diagram:
	@if [ -z "$(IN)" ]; then echo "uso: make diagram IN=diagrams_src/<slug>.diag"; exit 1; fi
	@$(PY) $(SKILL)/scripts/pipeline.py $(IN)

validate:
	@if [ -z "$(FILE)" ]; then echo "uso: make validate FILE=diagrams_src/<slug>.py [IR=<slug>.ir.json]"; exit 1; fi
	@$(PY) $(SKILL)/scripts/validate_code.py $(FILE) $(if $(IR),--ir $(IR),)

test:
	@cd $(SKILL) && ../../../$(PY) -m unittest discover -s tests -t .

evals:
	@cd $(SKILL) && ../../../$(PY) -m unittest tests.test_pipeline_evals -v

golden:
	@$(PY) $(SKILL)/tests/make_golden.py
