.PHONY: help

help:
	@echo "Usage:"
	@echo "  make test               CI: Run tests"
	@echo "  make format             CI: Format the code"

test:
	uv run pytest

format:
	uv run ruff format $$(git diff --name-only --cached -- '*.py')

check:
	uv run ruff check $$(git diff --name-only --cached -- '*.py')

type:
	uv run ty check $$(git diff --name-only --cached -- '*.py')

build:
	uv build

publish:
	uv publish

ci:
	$(MAKE) check
	$(MAKE) format
	$(MAKE) type
	$(MAKE) test