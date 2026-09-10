SHELL := /bin/bash

VENV := .venv
PIP  := $(VENV)/bin/pip
FMT  ?= png

.PHONY: help install check render all clean

help:
	@echo "targets disponibles:"
	@echo "  make install                        crea el venv e instala las dependencias"
	@echo "  make check                          verifica python, graphviz y diagrams"
	@echo "  make render FILE=ejemplo_aws.py     genera output/ejemplo_aws.png"
	@echo "  make render FILE=ejemplo_aws.py FMT=svg"
	@echo "  make all                            renderiza todos los .py de diagrams_src/"
	@echo "  make clean                          vacía output/"

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
	for f in diagrams_src/[!_]*.py; do FORMAT=$(FMT) ./render.sh "$$f"; done

clean:
	@find output -mindepth 1 ! -name .gitkeep -delete
	@echo "output/ vacío"
