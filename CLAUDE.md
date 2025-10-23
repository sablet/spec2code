# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**spec2code** is a specification-driven code generation and validation system that enables developers to define code structure as declarative YAML and automatically generate type-safe Python skeleton code. The system validates that implementations remain consistent with specifications and manages data flow as Directed Acyclic Graphs (DAGs).

Core principle: **Specification as Source of Truth**

## Development Commands

### Package Management
This project uses `uv` as the package manager. All Python commands should be run via `uv run`.

```bash
# Install dependencies
uv sync

# Add new packages
uv add <package_name>

# Add dev dependencies
uv add --dev <package_name>
```

### Primary Development Workflow

```bash
# Generate skeleton code from a specification
make gen [SPEC=specs/xxx.yaml]
# or: uv run python spec2code_cli.py gen specs/spec.yaml

# Execute DAG and run validation
make run [SPEC=specs/xxx.yaml]
# or: uv run python spec2code_cli.py run specs/spec.yaml

# Validate spec-implementation integrity
make validate [SPEC=specs/xxx.yaml]
# or: uv run python spec2code_cli.py validate specs/spec.yaml

# Run all specs at once
make gen-all      # Generate skeletons for all specs
make run-all      # Execute all specs
make validate-all # Validate all specs
```

### Testing & Quality

```bash
# Run full test suite (format + check + pytest)
make test

# Individual steps
make format       # Run ruff formatting
make check        # Run ruff linting
uv run pytest -v  # Run pytest with verbose output

# Run a single test file
uv run pytest packages/tests/test_integrity_validation.py -v

# Run a specific test function
uv run pytest packages/tests/test_integrity_validation.py::test_valid_project_passes -v
```

### Cleanup

```bash
make clean        # Remove all generated apps/
```

## Architecture

### Core System Flow

```
YAML Specification → [Engine] → Generated Skeleton Code
                         ↓
                  Validation & Execution
                         ↓
                  DAG Processing & Examples
```

### Directory Structure Philosophy

- **`packages/spec2code/`**: Core engine library - contains all generation, validation, and execution logic
- **`apps/`**: Generated applications - each spec generates an isolated app directory
- **`specs/`**: Specification files - YAML definitions that drive code generation
- **`packages/tests/`**: Test suite - pytest-based integration tests
- **`output/`**: Generated artifacts - reports, data, logs (gitignored)

### Key Components

#### Engine (`packages/spec2code/engine.py`)

The 600+ line core engine implements:

1. **Pydantic Data Models**: `Spec`, `Transform`, `Check`, `DataType`, `Example`, `DAGEdge`, `Parameter`, `Meta`
2. **Code Generation**: `generate_skeleton()` creates Python files with type annotations
3. **Type Annotation System**: Builds complex `Annotated` types with `Check[ref]` and `ExampleValue[data]`
4. **Validation Engine**: `Engine.validate_integrity()` checks spec-implementation alignment
5. **DAG Execution**: `Engine.run_dag()` topologically sorts and executes transforms
6. **Schema Validation**: JSON Schema validation for datatypes

#### Generated Code Structure

Each generated app follows this pattern:

```
apps/sample-pipeline/
├── __init__.py
├── checks/
│   ├── __init__.py
│   └── text_checks.py      # Validation functions
└── transforms/
    ├── __init__.py
    └── text_ops.py          # Processing functions
```

Generated functions include:
- Type annotations with `Annotated`, `Check`, and `ExampleValue` markers
- Embedded validation references in function signatures
- `TODO` markers for implementation
- Docstrings from spec descriptions

### Specification Format

YAML files define:
- **checks**: Validation function declarations
- **examples**: Test input/output pairs
- **datatypes**: Data structures with JSON Schema
- **transforms**: Processing functions with parameters and return types
- **dag**: Dependency relationships between transforms

Critical fields:
- `impl`: Module path in format `"module.path:function_name"`
- `file_path`: Where the function should exist (relative to app root)
- `datatype_ref`: References to datatypes for type safety
- `native`: Built-in Python types in format `"builtins:type"`

### Important Implementation Details

#### Schema Field Naming
The `DataType` model uses `schema_def` internally (aliased from `schema` in YAML) to avoid Pydantic's protected namespace conflicts. When working with datatypes in code, use `datatype.schema_def`.

#### File Generation Safety
The skeleton generator never overwrites existing files. It only creates files that don't exist, making it safe to run repeatedly without losing manual implementations.

#### Import Path Resolution
All generated code uses absolute imports based on the app name from `meta.name`. For example, with `meta.name: "sample-pipeline"`, generated imports are `apps.sample-pipeline.checks.text_checks:len_gt_0`.

#### Validation Categories
`validate_integrity()` checks five categories:
1. `check_functions`: Are check functions importable?
2. `check_locations`: Are functions in the expected files?
3. `transform_functions`: Are transform functions importable?
4. `transform_signatures`: Do parameters match the spec?
5. `example_schemas`: Does example data validate against schemas?

### Testing Architecture

**Framework**: pytest with fixtures

**Key Fixtures** (`packages/tests/conftest.py`):
- `temp_project_dir`: Isolated temporary directory
- `sample_spec_yaml`: Template specification data
- `spec_file`: Generated YAML file path
- `generated_project`: Project after skeleton generation
- `implemented_project`: Project with full implementations

Tests validate that integrity checking correctly detects:
- Missing implementations
- File relocations
- Signature mismatches
- Schema violations
- Multiple simultaneous errors

## Development Guidelines

### When Modifying the Engine

1. **Type Annotations**: All generated code must maintain type safety with `Annotated` types
2. **Backward Compatibility**: Spec format changes require version updates
3. **Error Messages**: Validation errors should include specific file locations and line numbers
4. **Test Coverage**: Add corresponding tests to `packages/tests/` for new validation logic

### When Adding New Features

1. Update the `Spec` Pydantic model if adding new spec fields
2. Update `generate_skeleton()` if changing code generation
3. Update `validate_integrity()` if adding new validation checks
4. Add tests demonstrating the feature and error cases
5. Update CLI subcommands in `main()` if exposing new functionality

### When Writing Specs

1. Use descriptive IDs for all entities (checks, transforms, datatypes, examples)
2. Ensure `impl` paths match `file_path` patterns consistently
3. Define datatypes before referencing them in transforms
4. Keep DAG edges acyclic (networkx will error on cycles)
5. Provide examples for all datatypes to enable validation

### Output Management

All generated reports, data files, and artifacts should go in `output/` subdirectories:
- `output/reports/`: HTML/text reports
- `output/data/`: JSON/CSV data files
- `output/logs/`: Execution logs
- `output/artifacts/`: Screenshots, images, etc.

## Dependencies

**Core**:
- `pydantic>=2.12`: Specification validation and modeling
- `pyyaml>=6.0`: YAML parsing
- `jsonschema>=4.25`: JSON Schema validation
- `networkx>=3.5`: DAG construction and cycle detection

**Dev**:
- `pytest>=8.4`: Testing framework

## Project Philosophy

This system enforces **declarative development**: specifications define structure, implementations provide logic, and the engine ensures consistency. The workflow encourages:

1. Team collaboration on specs before implementation
2. Automatic skeleton generation to jumpstart development
3. Continuous validation to catch spec-implementation drift
4. CI/CD integration for automated integrity checks

The separation of concerns enables specs to serve as living documentation that stays synchronized with code.
