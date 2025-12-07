```
# datamole: Technical Specification

## Overview
`datamole` (abbreviated as `dtm`) is a Python package and CLI tool designed to version, track, and manage datasets for ML and data science projects. It supports both programmatic access (as a Python module) and command-line interaction. It integrates with git and cloud storage for reproducible, collaborative data workflows.

---

## Functional Requirements

### 1. Initialization and `.datamole` file

#### Format
- File format: YAML (with `.datamole` extension)
- Git-tracked (committed to repository)
- Contains:
  ```yaml
  project: <project_name>
  data_directory: <relative_path>  # e.g., "data"
  current_version: <hash>           # Latest/canonical version
  backend_type: <type>              # "local", "gcs", "s3", "azure"
  versions:
    - hash: <version_hash>          # 8-character hex string
      timestamp: <iso8601>
      message: <optional_description>
  ```

#### Global Backend Configuration
- Backend configurations are stored in `~/.datamole/config.yaml` (NOT in `.datamole`)
- This allows teams to share `.datamole` while maintaining individual backend setups
- Format:
  ```yaml
  backends:
    local:
      remote_uri: /path/to/storage
    gcs:
      remote_uri: gs://bucket-name/path
      credentials_path: /path/to/credentials.json  # Optional
    s3:
      remote_uri: s3://bucket-name/path
      credentials_path: /path/to/credentials.json  # Optional
  ```

#### Backend Configuration
- **Backend Types**:
  - `local`: Local filesystem storage (default)
    - URI format: `/absolute/path/to/storage` or `file:///path/to/storage`
    - Useful for testing and simple use cases
  - `gcs`: Google Cloud Storage
    - URI format: `gs://bucket-name/path`
    - Auth: Implicit via `gcloud` CLI or credentials file
  - `s3`: Amazon S3
    - URI format: `s3://bucket-name/path`
    - Auth: Implicit via `aws` CLI or credentials file
  - `azure`: Azure Blob Storage
    - URI format: `https://account.blob.core.windows.net/container/path`
    - Auth: Implicit via `az` CLI or credentials file

- **Authentication**:
  - **Preferred**: Implicit authentication via cloud CLI tools (gcloud, aws, az)
  - **Fallback**: Explicit credentials via `credentials_path` in .datamole
  - Credentials files are NOT committed to git (add to .gitignore)

- **Configuration Methods**:
  1. **First-time setup**: Run `dtm config --backend <type> --remote-uri <uri> [--credentials-path <path>]`
     - Configures backend in `~/.datamole/config.yaml`
     - Only needs to be done once per backend type
  2. **During project init**: `dtm init --backend <type>`
     - Specifies which configured backend to use for this project
     - Backend must already be configured in global config
  3. **Auto-initialization**: On package install, default local backend is configured automatically
     - Default local storage: `~/.datamole/storage`

#### Command: `dtm init [--data-dir <path>] [--no-pull] [--backend <type>]`

**Case A: Fresh initialization (no `.datamole` exists)**
- Creates new `.datamole` file
- `--data-dir <path>`: Sets data directory (default: "data")
- `--backend <type>`: Storage backend type (default: "local")
  - Backend must be configured in `~/.datamole/config.yaml`
  - Use `dtm config --backend <type>` to configure if needed
- Calls `backend.setup(project_name)` to initialize project in remote storage
- Path must be relative to project root
- Does NOT require data directory to exist yet
- Does NOT download any data

**Case B: Existing `.datamole` (collaborator scenario)**
- Reads existing `.datamole` configuration (reads `backend_type`)
- Loads backend config from `~/.datamole/config.yaml`
- Verifies backend is accessible via `backend.setup()`
- Auto-downloads `current_version` to `data_directory`
- `--no-pull`: Skip automatic download
- `--backend` flag is ignored (backend type comes from `.datamole`)
- Creates `data_directory` if it doesn't exist

### 2. Version Tracking
- Command: `dtm add-version [--message <msg>]`
- Behavior:
  - Snapshots contents of configured `data_directory`
  - Validates that `data_directory` exists and is not empty
  - Generates random 8-character hex hash (e.g., `a3f5c912`)
    - Checks for collisions (regenerates if duplicate found)
  - Uploads full directory structure to remote storage at `<remote>/<project>/<hash>/`
  - **Transaction Safety**: Only updates `.datamole` if upload succeeds
    - If upload fails, `.datamole` remains unchanged
  - Adds version metadata to `.datamole`
  - Updates `current_version` to new hash automatically
  - Optional `--message` for version description
  - **Note**: For directories >1GB, consider implementing background upload (future enhancement)

### 3. Pulling Versions
- Command: `dtm pull [<version_hash>]`
- Behavior:
  - Downloads specified version from remote storage
  - Always extracts to configured `data_directory`
  - Creates `data_directory` if it doesn't exist
  - Overwrites existing contents (with confirmation prompt)
  - If no version specified, pulls `current_version`
  - Special keyword: `dtm pull latest` pulls most recent version

### 4. Backend Configuration
- Command: `dtm config --backend <type> --remote-uri <uri> [--credentials-path <path>]`
- Behavior:
  - Configures backend in `~/.datamole/config.yaml`
  - Only needs to be done once per backend type
  - Shared across all datamole projects
  - Examples:
    ```bash
    # Configure local backend
    dtm config --backend local --remote-uri /mnt/data/storage
    
    # Configure GCS backend
    dtm config --backend gcs --remote-uri gs://my-bucket/datamole
    
    # Configure S3 with explicit credentials
    dtm config --backend s3 --remote-uri s3://my-bucket/datamole \
      --credentials-path ~/.aws/credentials.json
    ```

### 5. Dual API and CLI Access
- Every core function in the CLI is available via Python API:
  ```python
  from datamole import DataMole
  
  dtm = DataMole()
  dtm.init(data_dir="data", backend="local")
  dtm.add_version(message="Initial dataset")
  dtm.list_versions()
  dtm.pull(version_hash="abc123")
  
  # Configure backends programmatically
  dtm.config_backend("gcs", "gs://bucket/path")
  ```
- CLI mirrors this via:
  ```bash
  dtm init --data-dir data --backend local
  dtm add-version --message "Initial dataset"
  dtm list-versions
  dtm pull abc123
  dtm config --backend gcs --remote-uri gs://bucket/path
  ```

---

## Core Functions

### DataMole Class Methods
- `init(data_dir="data", no_pull=False, backend="local")`: Initialize datamole in a repo
  - backend must be configured in `~/.datamole/config.yaml`
- `config_backend(backend, remote_uri, credentials_path=None)`: Configure storage backend in global config
- `add_version(message=None)`: Snapshot and track current data_directory state
  - Transaction-safe: only updates .datamole on successful upload
- `list_versions()`: Show all tracked versions with metadata
- `pull(version_hash=None)`: Retrieve version from remote (defaults to current_version)
- `current_version()`: Display currently checked out version
- `delete_version(version_hash)`: Remove a version from tracking and remote storage

### CLI Commands
- `dtm init [--data-dir <path>] [--no-pull] [--backend <type>]`: Initialize datamole
- `dtm config --backend <type> --remote-uri <uri> [--credentials-path <path>]`: Configure storage backend
- `dtm add-version [--message <msg>]`: Create new version snapshot
- `dtm list-versions`: List all versions
- `dtm pull [<hash>]`: Download version (defaults to current)
- `dtm current-version`: Show current version
- `dtm delete-version <hash>`: Delete a version

## Non-Functional Requirements
- Compatible with Python 3.8+
- Minimal external dependencies
- Uses `pyproject.toml` for packaging
- Logging and error handling for CLI
- Documentation and examples in README
- Unit tests with `pytest`

---

## File Structure
```
datamole/
  __init__.py
  core.py         # Main logic (DataMole class, DataMoleFileConfig)
  cli.py          # CLI parser using argparse
  config.py       # Config/environment utilities
  storage.py      # Storage backends (BackendType enum, StorageBackend ABC, LocalStorageBackend)
  versioning.py   # Version hash and tracking logic
  utils.py

tests/
  test_config.py
  test_storage.py
  test_global_config.py
  test_add_version.py
  test_integration.py

~/.datamole/          # User's home directory
  config.yaml         # Global backend configuration
  storage/            # Default local backend storage (if using local backend)

project_directory/
  .datamole           # Project-specific config (git-tracked)
  data/               # Data directory (git-ignored)

pyproject.toml
README.md
Contributing.md
```

## Workflows

### Workflow A: Data Owner (creating versions)
```bash
# First-time setup: Configure backend (only once)
$ dtm config --backend gcs --remote-uri gs://my-bucket/datamole
# Configured gcs backend in ~/.datamole/config.yaml

# ML project with existing data/ directory
cd my-ml-project/

# Initialize datamole
$ dtm init --data-dir data --backend gcs
# Initialized gcs backend for project
# Created .datamole file...

# Snapshot current state
$ dtm add-version --message "Initial training dataset"
# Generated version hash: a3f5c912
# Uploading to gcs storage...
# ✓ Version a3f5c912 created successfully

# Make changes to data/...
# Add another version
$ dtm add-version --message "Added validation split"

# Commit .datamole to git (data/ stays in .gitignore)
$ git add .datamole
$ git commit -m "Track dataset versions with datamole"
```

### Workflow B: Collaborator (cloning repo)
```bash
# Clone repo with .datamole file
$ git clone <repo>
$ cd my-ml-project/

# Initialize - automatically downloads current version
$ dtm init
# Creates data/ directory and downloads latest version

# Or skip download
$ dtm init --no-pull

# Later, pull a specific version
$ dtm pull abc123

# Or pull latest
$ dtm pull latest
```

## Example Usage
```bash
# List all available versions
$ dtm list-versions

# Check current version
$ dtm current-version

# Delete old version
$ dtm delete-version old-hash-123
```
```

