#!/usr/bin/env bash
# Development setup script for datamole

set -e

echo "Setting up datamole development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed."
    echo ""
    echo "Please install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "Or visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Ensure we're using Python 3.12
uv python pin 3.12

# Sync dependencies
echo "Installing dependencies..."
uv sync

# Install in development mode
echo "Installing datamole in development mode..."
uv pip install -e ".[dev]"

# Initialize default config (for development)
echo "Initializing default config..."
uv run python -c "from datamole.storage import initialize_default_config; initialize_default_config(); print('✓ Default config initialized at ~/.datamole/config.yaml')"

echo ""
echo "✓ Setup complete!"
echo ""
echo "You can now use:"
echo "  - 'uv run dtm' for CLI commands"
echo "  - 'uv run pytest' for running tests"
echo ""
echo "Or activate the virtual environment:"
echo "  source .venv/bin/activate"
echo "  dtm --help"
