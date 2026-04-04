# Makefile for local build helpers and CI release workflow dispatch.

RELEASE_WORKFLOW := Release / Cut Release
RELEASE_REF ?= main
RELEASE_TYPE ?= patch
DRY_RUN_REF ?= $(shell git rev-parse --abbrev-ref HEAD)

.PHONY: bump patch minor major release-dry-run build wheel pyinstaller

define run_release
	@gh workflow run "$(RELEASE_WORKFLOW)" --ref "$(1)" -f release_type="$(2)" -f dry_run="$(3)"
	@echo "Dispatched $(RELEASE_WORKFLOW) on ref '$(1)' with release_type='$(2)' dry_run='$(3)'"
endef

bump:
	@echo "Usage: make patch|minor|major or make release-dry-run RELEASE_TYPE=patch"

patch:
	$(call run_release,$(RELEASE_REF),patch,false)

minor:
	$(call run_release,$(RELEASE_REF),minor,false)

major:
	$(call run_release,$(RELEASE_REF),major,false)

release-dry-run:
	$(call run_release,$(DRY_RUN_REF),$(RELEASE_TYPE),true)


build:
	cd apps/api && uv build

wheel: build

pyinstaller:
	# build single-file for the current platform from apps/api/app/main.py
	cd apps/api && uv run pyinstaller --additional-hooks-dir hooks --onefile app/main.py --name anibridge
