# Copilot Instructions for kmb_tools

## Project Overview

`kmb_tools` is a Python data engineering toolkit. It provides reusable utilities and pipelines for data ingestion, transformation, and orchestration tasks.

## Stack & Environment

- **Language:** Python 3.x
- **Dependency management:** `pip` with `requirements.txt` (or `pyproject.toml` if using a build backend like `hatchling`/`setuptools`)
- **Virtual environment:** Use `venv` or `conda`; activate before running any commands

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Install package in editable mode (if pyproject.toml or setup.py exists)
pip install -e .
```

## Testing

```bash
# Run full test suite
pytest

# Run a single test file
pytest tests/test_<module>.py

# Run a single test by name
pytest tests/test_<module>.py::test_function_name

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=kmb_tools
```

## Linting & Formatting

```bash
# Lint
ruff check .

# Format
ruff format .

# Type checking
mypy kmb_tools/
```

## Architecture

> **Update this section as the project grows.**

```
kmb_tools/
├── kmb_tools/         # Main package source
│   ├── __init__.py
│   ├── ingestion/     # Data ingestion utilities (connectors, readers)
│   ├── transform/     # Transformation logic (cleaning, mapping, enrichment)
│   └── utils/         # Shared helpers (logging, config, retry logic)
├── tests/             # pytest test suite mirroring the package structure
├── pyproject.toml     # Project metadata and build config
└── requirements.txt   # Runtime dependencies
```

## Key Conventions

- **Module structure:** Each sub-package (`ingestion/`, `transform/`, etc.) should have its own `__init__.py` that exports the public API for that module.
- **Config:** Use environment variables (via `python-dotenv` or `os.environ`) for credentials and environment-specific settings — never hard-code them.
- **Logging:** Use the standard `logging` module rather than `print`. Configure a single root logger at the entry point; individual modules should use `logging.getLogger(__name__)`.
- **Error handling:** Raise typed, descriptive exceptions. Avoid bare `except:` clauses.
- **Type hints:** Add type annotations to all public functions and class methods.
- **Tests:** Mirror the package structure under `tests/`. Name test files `test_<module>.py` and test functions `test_<behavior>`.
