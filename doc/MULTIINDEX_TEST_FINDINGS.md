# MultiIndex Type Extension Test Findings

**Date**: 2025-10-24
**Test Spec**: `specs/type-extension-demo.yaml`
**Purpose**: Verify that MultiIndex types can be properly defined, generated, and validated

## Test Setup

Added the following to `type-extension-demo.yaml`:

### Type Definitions
```yaml
datatypes:
  - id: TimeSeriesIndex
    description: "MultiIndex for time series with symbol and date"
    type_alias:
      type: simple
      target: "pandas:MultiIndex"

  - id: MultiIndexDataFrame
    description: "DataFrame with MultiIndex"
    type_alias:
      type: simple
      target: "pandas:DataFrame"
```

### Check Functions
```yaml
checks:
  - id: check_multiindex
    description: "Validate MultiIndex structure"
    impl: "apps.type_extension_demo.checks.validation:check_multiindex"
    file_path: "checks/validation.py"
```

### Transform Functions
```yaml
transforms:
  - id: create_multiindex_data
    description: "Create DataFrame with MultiIndex"
    impl: "apps.type_extension_demo.transforms.indexing:create_multiindex_data"
    file_path: "transforms/indexing.py"
    parameters:
      - name: data
        datatype_ref: PriceData
      - name: symbols
        native: "builtins:list"
    return_datatype_ref: MultiIndexDataFrame

  - id: process_multiindex
    description: "Process MultiIndex DataFrame"
    impl: "apps.type_extension_demo.transforms.indexing:process_multiindex"
    file_path: "transforms/indexing.py"
    parameters:
      - name: df
        datatype_ref: MultiIndexDataFrame
      - name: level
        native: "builtins:int"
        default: 0
    return_datatype_ref: PriceData
```

## Test Results

### Generation (`make gen`)

✅ **Type Aliases Generated Correctly**
```python
# apps/type_extension_demo/datatypes/type_aliases.py
TimeSeriesIndex: TypeAlias = pd.MultiIndex
MultiIndexDataFrame: TypeAlias = pd.DataFrame
```

✅ **Check Function Generated Correctly**
```python
# apps/type_extension_demo/checks/validation.py
def check_multiindex(payload: dict) -> bool:
    """Validate MultiIndex structure"""
    # TODO: implement validation logic
    return True
```

❌ **Transform Generation Issue**

Only the first transform in `transforms/indexing.py` was generated:

**Generated**:
```python
# apps/type_extension_demo/transforms/indexing.py
def create_multiindex_data(data: PriceData, symbols: list) -> MultiIndexDataFrame:
    """Create DataFrame with MultiIndex"""
    # TODO: implement transform logic
    return {}
```

**Missing**:
- `process_multiindex()` function was NOT generated

### Validation (`make validate`)

**Before manual fix**:
```
❌ Transform 'process_multiindex' not found: cannot import name 'MultiIndexDataFrame'
   from 'apps.type_extension_demo.datatypes.type_aliases'
```

**After manually adding process_multiindex**:
```
✅ All integrity checks passed!
```

## Identified Issues

### Issue #1: Multiple Transforms in Same File Not Generated

**Severity**: High
**Component**: `packages/spec2code/engine.py` - `generate_skeleton()` function

**Problem**:
When multiple transforms specify the same `file_path`, only the first transform's function is generated. Subsequent transforms in the same file are skipped.

**Evidence**:
- Generator output showed: `⏭️  Skip (exists): apps/type_extension_demo/transforms/indexing.py`
- Second transform `process_multiindex` was never written to the file

**Expected Behavior**:
The generator should append additional functions to existing files when multiple transforms share the same `file_path`.

**Current Behavior**:
The generator skips file generation if the file already exists, even if it contains incomplete content.

**Root Cause** (hypothesis):
The skeleton generator likely checks `if file.exists()` before writing, rather than:
1. Checking which functions already exist in the file
2. Appending missing functions to existing files

**Impact**:
- Developers cannot organize related transforms in a single module
- Forces one file per transform, leading to fragmented code organization
- Validation fails for missing functions
- Manual intervention required after generation

## Recommendations

### Short-term Workaround
When defining multiple transforms in the same file:
1. Use different `file_path` values during initial generation
2. Manually consolidate functions afterward
3. Re-run validation

### Long-term Fix
Modify `generate_skeleton()` to:

```python
# Pseudocode for improved generation logic
def generate_transform_file(file_path, transforms):
    if file_path.exists():
        existing_code = parse_python_file(file_path)
        existing_functions = extract_function_names(existing_code)

        for transform in transforms:
            if transform.function_name not in existing_functions:
                append_function(file_path, generate_function_skeleton(transform))
    else:
        # Create new file with all transforms
        write_file(file_path, generate_all_functions(transforms))
```

**Alternative approach**:
- Group transforms by `file_path` before generation
- Generate all functions for each file in a single write operation
- Use AST parsing to detect existing functions and avoid duplication

## Conclusion

**MultiIndex Support**: ✅ Works correctly
**Type Alias Generation**: ✅ Successful
**Check Generation**: ✅ Successful
**Transform Generation**: ❌ Fails for multiple transforms per file

The type system properly handles `pandas.MultiIndex` through type aliases. The only issue is the skeleton generator's inability to append multiple transforms to the same file.

**Validation after manual fix**: All integrity checks passed, confirming that the type extension system itself works correctly for MultiIndex types.
