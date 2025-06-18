.PHONY: help

help:
	@echo "Usage:"
	@echo "  make test               CI: Run tests"
	@echo "  make format             CI: Format the code"

test:
	uv run pytest

format:
	uv run black .