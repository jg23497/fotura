.PHONY: help

help:
	@echo "Usage:"
	@echo "  make test               CI: Run tests"
	@echo "  make format             CI: Format the code"
	@echo "  make check              CI: Run the linter"
	@echo "  make type               CI: Type check the code"
	@echo "  make build              CI: Build the package"
	@echo "  make publish            CI: Publish the package"
	@echo "  make ci                 CI: Run all checks"

test:
	uv run pytest

format:
	uv run ruff format $$(git diff --name-only --cached -- '*.py')

check:
	uv run ruff check $$(git diff --name-only --cached -- '*.py') --fix

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