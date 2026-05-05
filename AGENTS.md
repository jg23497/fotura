# Agents

## Package management

Use `uv` for all dependency and environment management. Do not use `pip` directly.

```bash
uv run python -m pytest   # run tests
uv run ruff check .       # lint
uv run ruff format .      # format
uv run ty check .         # type check
```

Or use `make ci` to run all checks at once.

## Adding dependencies

```bash
uv add <package>           # runtime dependency
uv add --dev <package>     # development dependency
```

## Key conventions

- Cross-platform compatibility is required (Linux, MacOS, Windows). Always use OS-agnostic path construction.
- Use double-underscore (`__`) name mangling for private methods and attributes.
- Module-level constants have no underscore prefix (e.g. `SUPPORTED_EXTENSIONS`).
- Test behaviour, not implementation. Avoid over-mocking.
- Respect the dry-run flag: never modify the filesystem when it is set.

## Further reading

- [Development guide](docs/development.md) — setup, architecture, and design principles
- [Google Photos upload processor](docs/processors/google_photos_upload.md) — OAuth setup and processor usage
