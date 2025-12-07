# DataMole Implementation TODO

This document tracks the implementation tasks needed to align the codebase with the updated specification.

## Project Tools
- **Package Manager**: `uv` (NOT pip or python -m)
- **Testing**: Run tests with `uv run pytest`
- **Commands**: Use `uv run <command>` for all Python execution

## Current Status
- ✅ Specification updated with new design
- ✅ Design decisions documented
- ✅ Task 1 complete (DataMoleFileConfig updated)
- ⏳ Testing Task 1 implementation

---

## Task 1: Update DataMoleFileConfig class

**File:** `datamole/core.py`

### Changes needed:
1. Add `current_version: Optional[str] = None` field
2. Change `versions` from `List[str]` to `List[dict]` with structure:
   ```python
   {
       "hash": "<version_hash>",
       "timestamp": "<iso8601>",
       "message": "<optional_description>"
   }
   ```
3. Add validation that `data_directory` is a relative path (no leading `/` or drive letters)
4. Add helper method: `get_absolute_data_path()` to resolve data_directory to absolute path
5. Update `load()` to handle new version structure and current_version
6. Update `save()` to serialize new structure
7. Add method: `add_version_entry(hash, timestamp, message=None)` to append to versions list
8. Add method: `get_latest_version()` to return most recent version hash

### Dependencies:
- None

---

## Task 2: Update DataMole.init() method

**File:** `datamole/core.py`

### Changes needed:
1. Add `@property config` to lazily load DataMoleFileConfig
2. Update `init()` signature: `def init(self, data_dir="data", no_pull=False)`
3. Implement Case A logic (fresh init):
   - Use `DataMoleFileConfig.create()` instead of manual YAML
   - Set `data_directory` from parameter
   - No auto-pull behavior
4. Implement Case B logic (existing .datamole):
   - Load existing config
   - If `not no_pull` and `current_version` exists:
     - Call `self.pull()` to download current version
   - Print informative messages
5. Update `_config` attribute handling

### Dependencies:
- Task 1 must be complete

---

## Task 3: Update DataMole.add_version() method

**File:** `datamole/core.py`

### Changes needed:
1. Update signature: `def add_version(self, message=None)`
2. Remove `data_dir` parameter
3. Get data_directory from `self.config.data_directory`
4. Validate data_directory exists and has content
5. Call versioning module to compute hash (placeholder for now)
6. Generate timestamp (ISO 8601 format)
7. Call `self.config.add_version_entry(hash, timestamp, message)`
8. Update `self.config.current_version = hash`
9. Call storage module to upload (placeholder for now)

### Dependencies:
- Task 1 must be complete
- Task 2 must be complete

---

## Task 4: Update DataMole.pull() method

**File:** `datamole/core.py`

### Changes needed:
1. Rename from `pull_version` to `pull`
2. Update signature: `def pull(self, version_hash=None)`
3. Remove `target_path` parameter
4. If `version_hash` is None, use `self.config.current_version`
5. If `version_hash == "latest"`, use `self.config.get_latest_version()`
6. Validate version exists in config
7. Get absolute data path from `self.config.get_absolute_data_path()`
8. Create directory if it doesn't exist
9. Call storage module to download (placeholder for now)
10. Add confirmation prompt if directory has existing content

### Dependencies:
- Task 1 must be complete
- Task 2 must be complete

---

## Task 5: Update DataMole.list_versions() method

**File:** `datamole/core.py`

### Changes needed:
1. Use `self.config` property instead of manual file loading
2. Change from `yaml.load()` to `yaml.safe_load()` (security fix)
3. Display version metadata in formatted output:
   - Hash
   - Timestamp (human-readable format)
   - Message (if present)
   - Mark current_version with indicator (e.g., `*`)
4. Handle empty versions list gracefully

### Dependencies:
- Task 1 must be complete
- Task 2 must be complete

---

## Task 6: Update CLI to match new signatures

**File:** `datamole/cli.py`

### Changes needed:
1. Update `init` subparser:
   - Add `--data-dir` argument (default="data")
   - Add `--no-pull` flag
   - Update call: `dtm.init(data_dir=args.data_dir, no_pull=args.no_pull)`

2. Update `add-version` subparser:
   - Remove `data_dir` positional argument
   - Add `--message` optional argument
   - Update call: `dtm.add_version(message=args.message)`

3. Rename `pull-version` to `pull`:
   - Make `version_hash` optional (positional or none)
   - Remove `--to` argument
   - Update call: `dtm.pull(args.version_hash if hasattr(args, 'version_hash') else None)`

4. Update other commands to use new method names

### Dependencies:
- Tasks 1-5 must be complete

---

## Task 7: Update tests for new design

**File:** `tests/test_datamole.py`

### Changes needed:
1. Change JSON expectations to YAML in all tests
2. Update `test_init_creates_datamole_file`:
   - Check for `data_directory` field
   - Check for `current_version` field
   - Validate versions is list of dicts, not strings

3. Add `test_init_with_data_dir`:
   - Test custom data_dir parameter

4. Add `test_init_existing_with_auto_pull`:
   - Mock existing .datamole
   - Verify pull is called

5. Add `test_init_existing_with_no_pull`:
   - Mock existing .datamole
   - Verify pull is NOT called with --no-pull

6. Update `test_add_version`:
   - Remove data_dir argument
   - Check version entry structure
   - Verify current_version updated

7. Add `test_relative_path_validation`:
   - Test that absolute paths are rejected

8. Update all other tests to match new signatures

### Dependencies:
- Tasks 1-6 should be complete

---

## Task 8: Export DataMole in __init__.py

**File:** `datamole/__init__.py`

### Changes needed:
1. Add import: `from datamole.core import DataMole`
2. Add to `__all__`: `["DataMole"]`
3. Optionally add version info

### Example:
```python
"""
datamole - Dataset versioning for ML projects
"""

from datamole.core import DataMole

__version__ = "0.1.0"
__all__ = ["DataMole"]
```

### Dependencies:
- None (can be done anytime)

---

## Implementation Order

**Phase 1: Core Data Model**
1. Task 1 - DataMoleFileConfig updates
2. Task 8 - Export DataMole (can be done in parallel)

**Phase 2: Core Methods**
3. Task 2 - init() method
4. Task 3 - add_version() method
5. Task 4 - pull() method
6. Task 5 - list_versions() method

**Phase 3: Integration**
7. Task 6 - CLI updates
8. Task 7 - Test updates

---

## Notes
- Each task should be completed and tested before moving to the next
- Placeholder implementations are OK for storage and versioning modules
- Focus on getting the API and data model correct first
- Remote storage implementation can be deferred to later
