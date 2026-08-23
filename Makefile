HERMES_VENV_PYTHON ?= /home/brian/.hermes/hermes-agent/venv/bin/python
HERMES_HOME_DIR ?= $(HOME)/.hermes
PLUGIN_PACKAGE_DIR := $(CURDIR)/hermes-device-plugin/hermes_device_plugin
PLUGIN_LINK := $(HERMES_HOME_DIR)/plugins/hermes-device

SYSTEMD_USER_DIR := $(HOME)/.config/systemd/user
SERVICE_UNIT := $(SYSTEMD_USER_DIR)/hdp-bridge.service

.PHONY: dev-install dev-install-profile dev-uninstall test acceptance lint fmt fmt-check typecheck check \
	service-install service-uninstall service-status service-logs

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

# Runs hdp-bridge as a systemd --user service instead of a foreground `uv run
# hdp-bridge serve`. Requires `uv sync` to have already populated .venv/.
# Lingering means the unit starts at boot and keeps running after you log
# out, without needing root to manage the unit itself.
service-install:
	test -x "$(CURDIR)/.venv/bin/hdp-bridge" || (echo "Run 'uv sync' first" >&2 && exit 1)
	mkdir -p "$(SYSTEMD_USER_DIR)"
	sed -e "s#@REPO_ROOT@#$(CURDIR)#g" -e "s#@HERMES_HOME@#$(HERMES_HOME_DIR)#g" \
		deploy/systemd/hdp-bridge.service.in > "$(SERVICE_UNIT)"
	systemctl --user daemon-reload
	systemctl --user enable --now hdp-bridge.service
	loginctl enable-linger "$$(id -un)"
	@echo "hdp-bridge is now running as a systemd --user service."
	@echo "Check status: make service-status | Logs: make service-logs"

service-uninstall:
	-systemctl --user disable --now hdp-bridge.service
	rm -f "$(SERVICE_UNIT)"
	systemctl --user daemon-reload
	@echo "Service removed. Lingering left enabled; run 'loginctl disable-linger $$(id -un)' to undo it."

service-status:
	systemctl --user status hdp-bridge.service

service-logs:
	journalctl --user -u hdp-bridge.service -f

test:
	uv run pytest

acceptance:
	HDP_RUN_ACCEPTANCE=1 uv run pytest tests/acceptance/test_seed_success_criterion.py

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

fmt-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

check: lint fmt-check typecheck test
