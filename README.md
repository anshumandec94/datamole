# datamole

Simple data versioning for ML projects. Track, version, and share your datasets with minimal overhead.

## Features
- 🚀 Simple CLI interface (`dtm` command)
- 📦 Version datasets with automatic hashing
- 🏷️ Tag versions for easy reference
- 🔍 Smart lookup: pull by hash, prefix, or tag
- 💾 Multiple storage backends (local, GCS, S3, Azure)
- 🔒 Transaction-safe uploads
- 🤝 Collaboration-friendly with shared storage

## Installation

```bash
pip install datamole
```

After installation, the `dtm` command will be available globally.

## Quick Start

```bash
# Configure storage backend (one-time setup)
dtm config --backend local --remote-uri /path/to/shared/storage

# Initialize in your project
cd my-ml-project
dtm init

# Add your data and create a version
dtm add-version -m "Initial dataset" -t v1.0

# List versions
dtm list-versions

# Pull a specific version (by tag, hash, or prefix)
dtm pull v1.0
dtm pull abc123  # by hash prefix
dtm pull latest  # pull current version
```

## CLI Commands

### Setup & Configuration
```bash
# Configure storage backend
dtm config --backend local --remote-uri /path/to/storage

# Initialize project
dtm init [--data-dir data] [--backend local] [--no-pull]
```

### Version Management
```bash
# Create a new version
dtm add-version [-m "message"] [-t tag-name]

# Pull a version
dtm pull [version] [-f]

# List all versions
dtm list-versions

# Show current version
dtm current-version
```

## Python API

```python
from datamole.core import DataMole

# Initialize
dtm = DataMole()
dtm.init(data_dir="data", backend="local")

# Create versions
dtm.add_version(message="Initial dataset", tag="v1.0")

# Pull versions
dtm.pull("v1.0")
dtm.pull("abc123")  # by hash prefix
dtm.pull()  # pull current version
```

## Storage Backends

- **local**: Local filesystem storage
- **gcs**: Google Cloud Storage (coming soon)
- **s3**: AWS S3 (coming soon)
- **azure**: Azure Blob Storage (coming soon)

## Development

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended for development)

### Setup

```bash
# Clone repository
git clone https://github.com/anshumandec94/datamole.git
cd datamole

# Option 1: Use setup script (with uv)
chmod +x scripts/setup-dev.sh
./scripts/setup-dev.sh

# Option 2: Manual setup with uv
uv sync
uv pip install -e ".[dev]"

# Option 3: Traditional setup (without uv)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run tests
uv run pytest  # with uv
# or
pytest  # if venv is activated
```

### Contributing

See [CONTRIBUTING.md](Contributing.md) for development guidelines.

## License

MIT


