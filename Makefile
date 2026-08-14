HERMES_VENV_PYTHON ?= /home/brian/.hermes/hermes-agent/venv/bin/python
HERMES_HOME_DIR ?= $(HOME)/.hermes
PLUGIN_PACKAGE_DIR := $(CURDIR)/hermes-device-plugin/hermes_device_plugin
PLUGIN_LINK := $(HERMES_HOME_DIR)/plugins/hermes-device

.PHONY: dev-install dev-install-profile dev-uninstall test lint fmt fmt-check typecheck check

dev-install:
	mkdir -p "$(HERMES_HOME_DIR)/plugins"
	ln -sfn "$(PLUGIN_PACKAGE_DIR)" "$(PLUGIN_LINK)"
	uv pip install --python "$(HERMES_VENV_PYTHON)" -e ./hdp-spec
	@echo "Run: hermes plugins enable hermes-device"

dev-install-profile:
	test -n "$(PROFILE)"
	mkdir -p "$(HOME)/.hermes/profiles/$(PROFILE)/plugins"
	ln -sfn "$(PLUGIN_PACKAGE_DIR)" "$(HOME)/.hermes/profiles/$(PROFILE)/plugins/hermes-device"
	uv pip install --python "$(HERMES_VENV_PYTHON)" -e ./hdp-spec
	@echo "Run: HERMES_HOME=$(HOME)/.hermes/profiles/$(PROFILE) hermes plugins enable hermes-device"

dev-uninstall:
	rm -f "$(PLUGIN_LINK)"

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

fmt-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

check: lint fmt-check typecheck test

