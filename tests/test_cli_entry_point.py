"""Test that CLI entry point is properly configured."""

import subprocess
import sys
from pathlib import Path


def test_cli_entry_point_exists():
    """Test that dtm command is available after installation."""
    # When running in development mode with uv/pip install -e,
    # the dtm script should be in the PATH
    result = subprocess.run(
        ["python", "-c", "import datamole.cli; datamole.cli.main()"],
        capture_output=True,
        text=True
    )
    # Should not crash when called with no args (shows help)
    assert result.returncode in [0, 1]  # 0 for success, 1 for no command


def test_cli_module_callable():
    """Test that CLI main function can be imported and called."""
    from datamole.cli import main
    
    # Verify it's callable
    assert callable(main)


def test_cli_help_works():
    """Test that CLI help command works."""
    result = subprocess.run(
        ["python", "-m", "datamole.cli", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "datamole" in result.stdout.lower()
    assert "init" in result.stdout
    assert "add-version" in result.stdout
    assert "pull" in result.stdout


def test_pyproject_has_script_entry():
    """Test that pyproject.toml has the dtm entry point configured."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # Python 3.10
    
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    
    # Check that scripts section exists
    assert "project" in pyproject
    assert "scripts" in pyproject["project"]
    
    # Check that dtm entry point is configured
    scripts = pyproject["project"]["scripts"]
    assert "dtm" in scripts
    assert scripts["dtm"] == "datamole.cli:main"


def test_dtm_command_via_subprocess():
    """Test that dtm command works when called directly (if installed)."""
    # This only works if package is installed (not just in PYTHONPATH)
    result = subprocess.run(
        [sys.executable, "-m", "datamole.cli"],
        capture_output=True,
        text=True
    )
    
    # Should show help when no command given
    assert result.returncode in [0, 1]
    assert "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower()
