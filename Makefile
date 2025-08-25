# Makefile for version bumping, building, and packaging

PYTHON ?= $(shell command -v python3 || command -v python || echo python)

.PHONY: bump patch minor major tag build wheel pyinstaller

bump:
	@echo "Usage: make patch|minor|major"

patch:
	$(PYTHON) -m pip install --upgrade bump2version
	# run the bump2version executable from the same Python's bin dir so it
	# works inside virtualenvs even if python -m bump2version is not available
	$(PYTHON) -c "import sys,subprocess,os; vbin=os.path.dirname(sys.executable); script=os.path.join(vbin,'bump2version'); sys.exit(subprocess.call([script,'patch']))"

minor:
	$(PYTHON) -m pip install --upgrade bump2version
	$(PYTHON) -c "import sys,subprocess,os; vbin=os.path.dirname(sys.executable); script=os.path.join(vbin,'bump2version'); sys.exit(subprocess.call([script,'minor']))"

major:
	$(PYTHON) -m pip install --upgrade bump2version
	$(PYTHON) -c "import sys,subprocess,os; vbin=os.path.dirname(sys.executable); script=os.path.join(vbin,'bump2version'); sys.exit(subprocess.call([script,'major']))"

tag:
	# create an annotated tag from current VERSION
	tag=v$(shell cat VERSION)
	git tag -a $$tag -m "Release $$tag"
	git push --tags


build:
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

wheel: build

pyinstaller:
	$(PYTHON) -m pip install --upgrade pyinstaller
	# build single-file for the current platform from app/main.py (adjust as needed)
	pyinstaller --onefile app/main.py --name anibridge
