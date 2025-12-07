"""
Unit tests for DataMoleFileConfig class.
Tests the YAML loading, saving, validation, and helper methods.
"""

import os
import tempfile
import pytest
import yaml
from datamole.config import DataMoleFileConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp = tempfile.mkdtemp()
    yield temp
    # Cleanup
    import shutil
    shutil.rmtree(temp, ignore_errors=True)


def test_config_create_new(temp_dir):
    """Test creating a new .datamole config file."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    assert config.project == "test_project"
    assert config.data_directory == "data"
    assert config.current_version is None
    assert config.versions == []
    assert os.path.exists(config_path)


def test_config_validates_relative_path(temp_dir):
    """Test that create() rejects absolute paths for data_directory."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    with pytest.raises(ValueError, match="must be a relative path"):
        DataMoleFileConfig.create(
            file_path=config_path,
            project="test_project",
            data_directory="/absolute/path"
        )


def test_config_save_and_load(temp_dir):
    """Test saving and loading config with YAML."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    # Create and save
    DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    # Load it back
    loaded_config = DataMoleFileConfig.load(config_path)
    
    assert loaded_config.project == "test_project"
    assert loaded_config.data_directory == "data"
    assert loaded_config.current_version is None
    assert loaded_config.versions == []


def test_config_yaml_format(temp_dir):
    """Test that the saved YAML has correct structure."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    # Read the YAML directly
    with open(config_path) as f:
        data = yaml.safe_load(f)
    
    assert data["project"] == "test_project"
    assert data["data_directory"] == "data"
    assert data["current_version"] is None
    assert data["versions"] == []


def test_config_add_version_entry(temp_dir):
    """Test adding a version entry."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    # Add a version
    config.add_version_entry(
        version_hash="abc123",
        timestamp="2025-12-01T10:00:00",
        message="Initial version"
    )
    
    assert len(config.versions) == 1
    assert config.versions[0]["hash"] == "abc123"
    assert config.versions[0]["timestamp"] == "2025-12-01T10:00:00"
    assert config.versions[0]["message"] == "Initial version"
    
    # Verify it was saved
    loaded = DataMoleFileConfig.load(config_path)
    assert len(loaded.versions) == 1
    assert loaded.versions[0]["hash"] == "abc123"


def test_config_add_version_without_message(temp_dir):
    """Test adding a version entry without a message."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    config.add_version_entry(
        version_hash="def456",
        timestamp="2025-12-01T11:00:00"
    )
    
    assert len(config.versions) == 1
    assert config.versions[0]["hash"] == "def456"
    assert "message" not in config.versions[0]


def test_config_get_latest_version(temp_dir):
    """Test getting the latest version."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    # No versions yet
    assert config.get_latest_version() is None
    
    # Add versions
    config.add_version_entry("v1", "2025-12-01T10:00:00")
    assert config.get_latest_version() == "v1"
    
    config.add_version_entry("v2", "2025-12-01T11:00:00")
    assert config.get_latest_version() == "v2"
    
    config.add_version_entry("v3", "2025-12-01T12:00:00")
    assert config.get_latest_version() == "v3"


def test_config_has_version(temp_dir):
    """Test checking if a version exists."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    config.add_version_entry("abc123", "2025-12-01T10:00:00")
    
    assert config.has_version("abc123") is True
    assert config.has_version("nonexistent") is False


def test_config_get_version_info(temp_dir):
    """Test retrieving version metadata."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    config.add_version_entry(
        "abc123",
        "2025-12-01T10:00:00",
        "Test version"
    )
    
    info = config.get_version_info("abc123")
    assert info is not None
    assert info["hash"] == "abc123"
    assert info["timestamp"] == "2025-12-01T10:00:00"
    assert info["message"] == "Test version"
    
    # Non-existent version
    assert config.get_version_info("nonexistent") is None


def test_config_get_absolute_data_path(temp_dir):
    """Test resolving data_directory to absolute path."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    abs_path = config.get_absolute_data_path()
    expected_path = os.path.abspath(os.path.join(temp_dir, "data"))
    
    assert abs_path == expected_path


def test_config_get_absolute_data_path_nested(temp_dir):
    """Test resolving nested data_directory path."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="datasets/raw"
    )
    
    abs_path = config.get_absolute_data_path()
    expected_path = os.path.abspath(os.path.join(temp_dir, "datasets/raw"))
    
    assert abs_path == expected_path


def test_config_update_current_version(temp_dir):
    """Test updating current_version field."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    config = DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    # Update current_version
    config.current_version = "abc123"
    config.save()
    
    # Load and verify
    loaded = DataMoleFileConfig.load(config_path)
    assert loaded.current_version == "abc123"


def test_config_load_nonexistent_file():
    """Test loading a non-existent config file."""
    with pytest.raises(FileNotFoundError, match="No .datamole file found"):
        DataMoleFileConfig.load("/nonexistent/path/.datamole")


def test_config_create_in_nonexistent_directory():
    """Test creating config in non-existent directory."""
    with pytest.raises(FileNotFoundError, match="Directory does not exist"):
        DataMoleFileConfig.create(
            file_path="/nonexistent/dir/.datamole",
            project="test_project"
        )


def test_config_prevents_duplicate_creation(temp_dir):
    """Test that create() prevents overwriting existing file."""
    config_path = os.path.join(temp_dir, ".datamole")
    
    # Create first time
    DataMoleFileConfig.create(
        file_path=config_path,
        project="test_project",
        data_directory="data"
    )
    
    # Try to create again
    with pytest.raises(FileExistsError, match="File already exists"):
        DataMoleFileConfig.create(
            file_path=config_path,
            project="another_project",
            data_directory="other_data"
        )
