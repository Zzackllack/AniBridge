# Makefile for version bumping, building, and packaging

PUSH ?= ask

.PHONY: bump patch minor major tag build wheel pyinstaller

bump:
	@echo "Usage: make patch|minor|major"

patch:
	uv tool run bump2version patch
	# push the new commit and tag to origin so CI triggers on the pushed tag
	@/bin/sh -c ' \
	if [ "$(PUSH)" = "true" ]; then \
		git push origin HEAD && git push origin --tags; \
	elif [ "$(PUSH)" = "ask" ]; then \
		printf "Push commit and tag to origin? [y/N] "; read -r ans; \
		if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
			git push origin HEAD && git push origin --tags; \
		else \
			echo "Skipping push"; \
		fi; \
	else \
		echo "PUSH=$(PUSH) -> skipping git push"; \
	fi'

minor:
	uv tool run bump2version minor
	# push the new commit and tag to origin so CI triggers on the pushed tag
	@/bin/sh -c ' \
	if [ "$(PUSH)" = "true" ]; then \
		git push origin HEAD && git push origin --tags; \
	elif [ "$(PUSH)" = "ask" ]; then \
		printf "Push commit and tag to origin? [y/N] "; read -r ans; \
		if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
			git push origin HEAD && git push origin --tags; \
		else \
			echo "Skipping push"; \
		fi; \
	else \
		echo "PUSH=$(PUSH) -> skipping git push"; \
	fi'

major:
	uv tool run bump2version major
	# push the new commit and tag to origin so CI triggers on the pushed tag
	@/bin/sh -c ' \
	if [ "$(PUSH)" = "true" ]; then \
		git push origin HEAD && git push origin --tags; \
	elif [ "$(PUSH)" = "ask" ]; then \
		printf "Push commit and tag to origin? [y/N] "; read -r ans; \
		if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
			git push origin HEAD && git push origin --tags; \
		else \
			echo "Skipping push"; \
		fi; \
	else \
		echo "PUSH=$(PUSH) -> skipping git push"; \
	fi'

tag:
	# create an annotated tag from current VERSION
	tag=v$(shell cat VERSION)
	git tag -a $$tag -m "Release $$tag"
	git push --tags


build:
	uv run --with build python -m build

wheel: build

pyinstaller:
	# build single-file for the current platform from app/main.py (adjust as needed)
	uv run --with pyinstaller pyinstaller --onefile app/main.py --name anibridge
