# Makefile for version bumping, building, and packaging

PUSH ?= ask

.PHONY: bump patch minor major tag build wheel pyinstaller

define run_bump
	@/bin/sh -eu -c ' \
	part="$(1)"; \
	should_push="$(PUSH)"; \
	if [ "$$should_push" = "ask" ]; then \
		printf "Push commit and tag to origin after bump? [y/N] "; \
		read -r ans; \
		case "$$ans" in \
			y|Y) should_push=true ;; \
			*) should_push=false ;; \
		esac; \
	fi; \
	before=$$(cat VERSION); \
	uv run bump2version "$$part"; \
	after=$$(cat VERSION); \
	echo "Version bumped: $$before -> $$after"; \
	if [ "$$should_push" = "true" ]; then \
		git push --atomic --follow-tags origin HEAD; \
		echo "Pushed commit and tag for $$after to origin"; \
	else \
		echo "Created local commit and tag for $$after; not pushed to origin"; \
	fi'
endef

bump:
	@echo "Usage: make patch|minor|major"

patch:
	$(call run_bump,patch)

minor:
	$(call run_bump,minor)

major:
	$(call run_bump,major)

tag:
	# create an annotated tag from current VERSION
	tag=v$(shell cat VERSION)
	git tag -a $$tag -m "Release $$tag"
	git push --tags


build:
	uv build

wheel: build

pyinstaller:
	# build single-file for the current platform from app/main.py (adjust as needed)
	uv run pyinstaller --additional-hooks-dir hooks --onefile app/main.py --name anibridge
