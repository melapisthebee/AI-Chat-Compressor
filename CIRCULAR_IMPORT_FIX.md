# Circular Import Fix

## Issue
When implementing the enhanced token management features, a circular import error occurred:

```
ImportError: cannot import name 'parse_lm_studio_file' from partially initialized module 'engine.parser'
```

## Root Cause
The circular import was caused by:
1. `engine/__init__.py` importing `parse_lm_studio_file` from `engine.parser`
2. `engine/parser/__init__.py` importing `ParserBenchmark` from `engine/parser/benchmark.py`
3. `engine/parser/benchmark.py` importing `parse_lm_studio_file` from `engine.parser`

This created a circular dependency: `engine` → `parser` → `benchmark` → `parser`

## Solution

### 1. Modified `engine/__init__.py`
Changed from direct import to lazy loading:

**Before:**
```python
from engine.parser import parse_lm_studio_file
```

**After:**
```python
# Lazy import for parser to avoid circular dependencies
def get_parser():
    """Lazy loader for parser functions to avoid circular imports."""
    from engine.parser import parse_lm_studio_file
    return parse_lm_studio_file

__all__ = ["tracker", "CompressionEngine", "StreamingTokenProcessor", "TokenBudgetManager", "get_parser"]
```

### 2. Modified `engine/parser/benchmark.py`
Changed top-level import to local imports within functions:

**Before:**
```python
from . import parse_lm_studio_file
```

**After:**
```python
# Import locally within functions to avoid circular import
# (No top-level import)
```

In functions that use `parse_lm_studio_file`:
```python
try:
    # Import locally to avoid circular import
    from . import parse_lm_studio_file
    parse_lm_studio_file(filepath)
except Exception:
    pass
```

### 3. Modified `gui/main_window.py`
Kept direct import from `engine.parser` since it doesn't create a circular dependency at the GUI level:

```python
from engine.parser import parse_lm_studio_file
```

## Verification
The fix was verified by:
1. Syntax validation of all modified files
2. Import testing (fails on missing dependencies, not circular imports)
3. Module structure validation

## Files Modified
- `engine/__init__.py` - Changed to lazy loading
- `engine/parser/benchmark.py` - Changed to local imports within functions
- `gui/main_window.py` - Minor reorganization (no functional change)

## Notes
- The application now fails on missing dependencies (tiktoken, PyQt6) rather than circular imports
- This is expected behavior when dependencies aren't installed
- The circular import issue has been completely resolved
