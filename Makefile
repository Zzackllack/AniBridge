# Makefile for version bumping, building, and packaging

PYTHON ?= $(shell command -v python3 || command -v python || echo python)
PUSH ?= ask

.PHONY: bump patch minor major tag build wheel pyinstaller

bump:
	@echo "Usage: make patch|minor|major"

patch:
	# Ensure pip is available (uv and some system python builds omit it by default)
	@$(PYTHON) -m ensurepip --upgrade >/dev/null 2>&1 || true
	$(PYTHON) -m pip install --upgrade bump2version
	# run the bump2version executable from the same Python's bin dir so it
	# works inside virtualenvs even if python -m bump2version is not available
	$(PYTHON) -c "import sys,subprocess,os; vbin=os.path.dirname(sys.executable); script=os.path.join(vbin,'bump2version'); sys.exit(subprocess.call([script,'patch']))"
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
	@$(PYTHON) -m ensurepip --upgrade >/dev/null 2>&1 || true
	$(PYTHON) -m pip install --upgrade bump2version
	$(PYTHON) -c "import sys,subprocess,os; vbin=os.path.dirname(sys.executable); script=os.path.join(vbin,'bump2version'); sys.exit(subprocess.call([script,'minor']))"
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
	@$(PYTHON) -m ensurepip --upgrade >/dev/null 2>&1 || true
	$(PYTHON) -m pip install --upgrade bump2version
	$(PYTHON) -c "import sys,subprocess,os; vbin=os.path.dirname(sys.executable); script=os.path.join(vbin,'bump2version'); sys.exit(subprocess.call([script,'major']))"
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
	@$(PYTHON) -m ensurepip --upgrade >/dev/null 2>&1 || true
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

wheel: build

pyinstaller:
	@$(PYTHON) -m ensurepip --upgrade >/dev/null 2>&1 || true
	$(PYTHON) -m pip install --upgrade pyinstaller
	# build single-file for the current platform from app/main.py (adjust as needed)
	pyinstaller --onefile app/main.py --name anibridge
