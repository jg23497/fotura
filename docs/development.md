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

### Setup

Obtain the source code

```
git clone https://github.com/jg23497/fotura.git
cd fotura
```

We use uv for dependency management. To install it:

#### MacOS and Linux (Unix-like systems)

<details>
<summary>Expand instructions</summary>

Install uv using the standalone installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
</details>

#### Windows

<details>
<summary>Expand instructions</summary>

Install uv using one of these methods:

**Option 1: Using PowerShell (recommended)**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Option 2: Using pip**

```cmd
pip install uv
```

**Option 3: Using winget**

```cmd
winget install astral-sh.uv
```
</details>

### Run Fotura

Run the following commands:

```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate # MacOS and Linux
.venv\Scripts\activate # Windows only

# Install the dependencies and package in editable mode
uv pip install -e .
```

This will make the `fotura` command available during development. Next time, you will only need to activate
the virtual environment and run `fotura`.

Alternatively, you can also use `uv run`:

```
uv run src/fotura/main.py
```

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
