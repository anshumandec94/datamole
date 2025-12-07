"""
Tests for global backend configuration and new storage architecture.
"""

import pytest
import os
import shutil
from pathlib import Path
import yaml

from datamole.storage import (
    BackendType,
    get_datamole_dir,
    get_config_path,
    save_backend_config,
    load_backend_config,
    initialize_default_config,
    create_storage_backend,
    LocalStorageBackend,
    StorageError
)


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Create a temporary home directory for testing."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    yield fake_home


@pytest.fixture
def clean_datamole_dir(temp_home):
    """Ensure ~/.datamole directory is clean for each test."""
    datamole_dir = temp_home / ".datamole"
    if datamole_dir.exists():
        shutil.rmtree(datamole_dir)
    yield datamole_dir


class TestBackendType:
    """Tests for BackendType enum."""
    
    def test_enum_values(self):
        """Test that enum has expected values."""
        assert BackendType.LOCAL.value == "local"
        assert BackendType.GCS.value == "gcs"
        assert BackendType.S3.value == "s3"
        assert BackendType.AZURE.value == "azure"
    
    def test_from_string_valid(self):
        """Test converting valid strings to enum."""
        assert BackendType.from_string("local") == BackendType.LOCAL
        assert BackendType.from_string("LOCAL") == BackendType.LOCAL
        assert BackendType.from_string("gcs") == BackendType.GCS
        assert BackendType.from_string("s3") == BackendType.S3
        assert BackendType.from_string("azure") == BackendType.AZURE
    
    def test_from_string_invalid(self):
        """Test that invalid strings raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported backend type"):
            BackendType.from_string("invalid")


class TestGlobalConfig:
    """Tests for global configuration management."""
    
    def test_get_datamole_dir_creates_directory(self, clean_datamole_dir):
        """Test that get_datamole_dir creates directory if it doesn't exist."""
        assert not clean_datamole_dir.exists()
        
        datamole_dir = get_datamole_dir()
        
        assert datamole_dir.exists()
        assert datamole_dir.is_dir()
    
    def test_get_config_path(self, clean_datamole_dir):
        """Test that get_config_path returns correct path."""
        config_path = get_config_path()
        
        assert config_path.name == "config.yaml"
        assert config_path.parent.name == ".datamole"
    
    def test_save_backend_config_creates_file(self, clean_datamole_dir):
        """Test saving backend config creates config file."""
        save_backend_config(BackendType.LOCAL, "/path/to/storage")
        
        config_path = get_config_path()
        assert config_path.exists()
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert "backends" in config
        assert "local" in config["backends"]
        assert config["backends"]["local"]["remote_uri"] == "/path/to/storage"
    
    def test_save_backend_config_with_credentials(self, clean_datamole_dir):
        """Test saving backend config with credentials path."""
        save_backend_config(
            BackendType.GCS,
            "gs://bucket/path",
            credentials_path="/path/to/creds.json"
        )
        
        config_path = get_config_path()
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert config["backends"]["gcs"]["remote_uri"] == "gs://bucket/path"
        assert config["backends"]["gcs"]["credentials_path"] == "/path/to/creds.json"
    
    def test_save_backend_config_updates_existing(self, clean_datamole_dir):
        """Test that saving updates existing backend config."""
        # Save initial config
        save_backend_config(BackendType.LOCAL, "/old/path")
        
        # Update with new path
        save_backend_config(BackendType.LOCAL, "/new/path")
        
        config_path = get_config_path()
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert config["backends"]["local"]["remote_uri"] == "/new/path"
    
    def test_save_backend_config_preserves_other_backends(self, clean_datamole_dir):
        """Test that saving one backend doesn't affect others."""
        # Save multiple backends
        save_backend_config(BackendType.LOCAL, "/local/path")
        save_backend_config(BackendType.GCS, "gs://bucket/path")
        
        # Update local
        save_backend_config(BackendType.LOCAL, "/new/local/path")
        
        config_path = get_config_path()
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert config["backends"]["local"]["remote_uri"] == "/new/local/path"
        assert config["backends"]["gcs"]["remote_uri"] == "gs://bucket/path"
    
    def test_load_backend_config_success(self, clean_datamole_dir):
        """Test loading existing backend config."""
        save_backend_config(BackendType.LOCAL, "/path/to/storage")
        
        config = load_backend_config(BackendType.LOCAL)
        
        assert config["remote_uri"] == "/path/to/storage"
    
    def test_load_backend_config_no_file(self, clean_datamole_dir):
        """Test loading config when file doesn't exist."""
        with pytest.raises(StorageError, match="Global config file not found"):
            load_backend_config(BackendType.LOCAL)
    
    def test_load_backend_config_backend_not_configured(self, clean_datamole_dir):
        """Test loading config for unconfigured backend."""
        # Save config for local only
        save_backend_config(BackendType.LOCAL, "/path")
        
        # Try to load GCS
        with pytest.raises(StorageError, match="Backend 'gcs' not configured"):
            load_backend_config(BackendType.GCS)
    
    def test_initialize_default_config(self, clean_datamole_dir):
        """Test initializing default config."""
        initialize_default_config()
        
        config_path = get_config_path()
        assert config_path.exists()
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert "backends" in config
        assert "local" in config["backends"]
        assert "remote_uri" in config["backends"]["local"]
    
    def test_initialize_default_config_idempotent(self, clean_datamole_dir):
        """Test that initialize_default_config doesn't overwrite existing config."""
        # Create custom config
        save_backend_config(BackendType.LOCAL, "/custom/path")
        
        # Try to initialize default
        initialize_default_config()
        
        # Verify custom config is preserved
        config = load_backend_config(BackendType.LOCAL)
        assert config["remote_uri"] == "/custom/path"


class TestStorageBackendFactory:
    """Tests for create_storage_backend factory function."""
    
    def test_create_local_backend(self, clean_datamole_dir, tmp_path):
        """Test creating local backend from config."""
        storage_path = tmp_path / "storage"
        save_backend_config(BackendType.LOCAL, str(storage_path))
        
        backend = create_storage_backend(BackendType.LOCAL)
        
        assert isinstance(backend, LocalStorageBackend)
        assert backend.base_path == storage_path
    
    def test_create_backend_no_config(self, clean_datamole_dir):
        """Test creating backend when not configured."""
        with pytest.raises(StorageError, match="Global config file not found"):
            create_storage_backend(BackendType.LOCAL)
    
    def test_create_backend_not_implemented(self, clean_datamole_dir):
        """Test creating backend types that aren't implemented yet."""
        save_backend_config(BackendType.GCS, "gs://bucket/path")
        
        with pytest.raises(NotImplementedError, match="GCS backend not yet implemented"):
            create_storage_backend(BackendType.GCS)


class TestLocalStorageBackendSetup:
    """Tests for LocalStorageBackend.setup() method."""
    
    def test_setup_creates_project_directory(self, clean_datamole_dir, tmp_path):
        """Test that setup creates project directory."""
        storage_path = tmp_path / "storage"
        save_backend_config(BackendType.LOCAL, str(storage_path))
        
        backend = create_storage_backend(BackendType.LOCAL)
        backend.setup("test_project")
        
        project_path = storage_path / "test_project"
        assert project_path.exists()
        assert project_path.is_dir()
    
    def test_setup_verifies_write_access(self, clean_datamole_dir, tmp_path):
        """Test that setup verifies write access."""
        storage_path = tmp_path / "storage"
        save_backend_config(BackendType.LOCAL, str(storage_path))
        
        backend = create_storage_backend(BackendType.LOCAL)
        
        # Should not raise error
        backend.setup("test_project")
    
    def test_setup_idempotent(self, clean_datamole_dir, tmp_path):
        """Test that setup can be called multiple times."""
        storage_path = tmp_path / "storage"
        save_backend_config(BackendType.LOCAL, str(storage_path))
        
        backend = create_storage_backend(BackendType.LOCAL)
        
        # Call setup twice
        backend.setup("test_project")
        backend.setup("test_project")  # Should not raise error
        
        project_path = storage_path / "test_project"
        assert project_path.exists()
