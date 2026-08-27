.PHONY: help test format check fix type build publish ci

help:
	@echo "Usage:"
	@echo "  make test               CI: Run tests"
	@echo "  make format             CI: Check code formatting"
	@echo "  make check              CI: Run the linter"
	@echo "  make type               CI: Type check the code"
	@echo "  make build              CI: Build the package"
	@echo "  make publish            CI: Publish the package"
	@echo "  make ci                 CI: Run all verification checks"
	@echo "  make fix                Fix staged Python files, or all files if none are staged"

test:
	uv run python -m pytest

format:
	uv run ruff format --check .

check:
	uv run ruff check .

fix:
	uv run ruff format $$(git diff --name-only --cached --diff-filter=AM -- '*.py')
	uv run ruff check $$(git diff --name-only --cached --diff-filter=AM -- '*.py') --fix

type:
	uv run ty check .

build:
	uv build

publish:
	uv publish

ci:
	$(MAKE) check
	$(MAKE) format
	$(MAKE) type
	$(MAKE) test
