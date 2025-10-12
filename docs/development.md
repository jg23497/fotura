# Development

## Principles

### Compatibility

- The application must be compatible with Linux, MacOS and Windows. Bear this in mind when
  constructing paths in particular, always preferring OS-agnostic approaches.

### Testing

- Test behaviour rather than the implementations, which will also mean
  avoiding an overuse of mocks.

### Architecture

- Design for extensibility so that functionality can be plugged in without requiring significant changes to core
  classes (e.g. see the `conflict_resolution`, `preprocessors` and `postprocessors` modules).

### Processing

- Respect the dry run flag. When the dry run flag is enabled, do not modify the filesystem.
- Fail fast. Ensure that failing processes do not continue to run in case of unintended consequences or harm to
  the user's photo library.

## How to

### Run PhotoTidy in development

In development, access the main entrypoint like so:

```bash
uv run src/photo_tidy/main.py
```

Alternatively, install the package in editable mode:

```bash
uv pip install -e .
```

This will make the `phototidy` command available for testing during development.

### Run tests

For Unix-like systems, use the [Makefile](../Makefile) (e.g. `make test`, `make ci`).

Otherwise:

```bash
uv run pytest
```

### Add development dependencies

```
uv add --dev <name>
```
