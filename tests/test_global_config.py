"""
Tests for global backend configuration and new storage architecture.
"""

import pytest
import shutil
import yaml

from datamole.storage import (
    BackendType,
    create_storage_backend,
    LocalStorageBackend,
    StorageError
)
from datamole.config.global_config import GlobalConfig


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
    # Clear singleton cache to ensure each test starts fresh
    GlobalConfig._instance = None
    yield datamole_dir
    # Clean up singleton after test
    GlobalConfig._instance = None


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
    
    def test_get_config_dir_creates_directory(self, clean_datamole_dir):
        """Test that get_config_dir creates directory if it doesn't exist."""
        assert not clean_datamole_dir.exists()
        
        config_dir = GlobalConfig.get_config_dir()
        
        assert config_dir == clean_datamole_dir
    
    def test_get_config_path(self, clean_datamole_dir):
        """Test that get_config_path returns correct path."""
        config_path = GlobalConfig.get_config_path()
        
        assert config_path.name == "config.yaml"
        assert config_path.parent.name == ".datamole"
    
    def test_save_backend_config_creates_file(self, clean_datamole_dir):
        """Test saving backend config creates config file."""
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path="/path/to/storage")
        global_config.save()
        
        config_path = GlobalConfig.get_config_path()
        assert config_path.exists()
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert "backends" in config
        assert "local" in config["backends"]
        assert config["backends"]["local"]["storage_path"] == "/path/to/storage"
    
    def test_save_backend_config_with_credentials(self, clean_datamole_dir):
        """Test saving backend config with credentials path."""
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(
            BackendType.GCS,
            service_account_json="/path/to/creds.json",
            default_bucket="my-bucket"
        )
        global_config.save()
        
        config_path = GlobalConfig.get_config_path()
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert config["backends"]["gcs"]["default_bucket"] == "my-bucket"
        assert config["backends"]["gcs"]["service_account_json"] == "/path/to/creds.json"
    
    def test_save_backend_config_updates_existing(self, clean_datamole_dir):
        """Test that saving updates existing backend config."""
        # Save initial config
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path="/old/path")
        global_config.save()
        
        # Update with new path
        global_config = GlobalConfig.reload()
        global_config.set_backend_config(BackendType.LOCAL, storage_path="/new/path")
        global_config.save()
        
        config_path = GlobalConfig.get_config_path()
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert config["backends"]["local"]["storage_path"] == "/new/path"
    
    def test_save_backend_config_preserves_other_backends(self, clean_datamole_dir):
        """Test that saving one backend doesn't affect others."""
        # Save multiple backends
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path="/local/path")
        global_config.set_backend_config(BackendType.GCS, default_bucket="my-bucket")
        global_config.save()
        
        # Update local
        global_config = GlobalConfig.reload()
        global_config.set_backend_config(BackendType.LOCAL, storage_path="/new/local/path")
        global_config.save()
        
        config_path = GlobalConfig.get_config_path()
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert config["backends"]["local"]["storage_path"] == "/new/local/path"
        assert config["backends"]["gcs"]["default_bucket"] == "my-bucket"
    
    def test_load_backend_config_success(self, clean_datamole_dir):
        """Test loading existing backend config."""
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path="/path/to/storage")
        global_config.save()
        
        loaded_config = GlobalConfig.load()
        config = loaded_config.get_backend_config(BackendType.LOCAL)
        
        assert config["storage_path"] == "/path/to/storage"
    
    def test_load_backend_config_no_file(self, clean_datamole_dir):
        """Test loading config when file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Global datamole configuration not found"):
            GlobalConfig.load()
    
    def test_load_backend_config_backend_not_configured(self, clean_datamole_dir):
        """Test loading config for unconfigured backend."""
        # Save config for local only
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path="/path")
        global_config.save()
        
        # Try to load GCS
        loaded_config = GlobalConfig.load()
        with pytest.raises(RuntimeError, match="Backend 'gcs' is not configured"):
            loaded_config.get_backend_config(BackendType.GCS)
    
    def test_initialize_default_config(self, clean_datamole_dir):
        """Test initializing default config."""
        global_config = GlobalConfig.initialize_defaults()
        
        config_path = GlobalConfig.get_config_path()
        assert config_path.exists()
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert "backends" in config
        assert "local" in config["backends"]
        assert "storage_path" in config["backends"]["local"]
    
    def test_initialize_default_config_idempotent(self, clean_datamole_dir):
        """Test that initialize_defaults creates config if missing."""
        # Initialize defaults
        global_config1 = GlobalConfig.initialize_defaults()
        
        # Get original storage path
        original_path = global_config1.get_backend_config(BackendType.LOCAL)["storage_path"]
        
        # Initialize again (loads existing via singleton)
        global_config2 = GlobalConfig.load()
        
        # Verify path is same (config not overwritten)
        assert global_config2.get_backend_config(BackendType.LOCAL)["storage_path"] == original_path


class TestStorageBackendFactory:
    """Tests for create_storage_backend factory function."""
    
    def test_create_local_backend(self, clean_datamole_dir, tmp_path):
        """Test creating local backend from config."""
        storage_path = tmp_path / "storage"
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path=str(storage_path))
        global_config.save()
        
        loaded_config = GlobalConfig.load()
        backend_config = loaded_config.get_backend_config(BackendType.LOCAL)
        backend = create_storage_backend(BackendType.LOCAL, backend_config)
        
        assert isinstance(backend, LocalStorageBackend)
        assert backend.base_path == storage_path
    
    def test_create_backend_no_config(self, clean_datamole_dir):
        """Test creating backend when not configured."""
        with pytest.raises(FileNotFoundError, match="Global datamole configuration not found"):
            global_config = GlobalConfig.load()
    
    def test_create_backend_not_implemented(self, clean_datamole_dir):
        """Test creating backend types that aren't implemented yet."""
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.GCS, default_bucket="my-bucket")
        global_config.save()
        
        loaded_config = GlobalConfig.load()
        backend_config = loaded_config.get_backend_config(BackendType.GCS)
        with pytest.raises(NotImplementedError, match="GCS backend not yet implemented"):
            create_storage_backend(BackendType.GCS, backend_config)


class TestLocalStorageBackendSetup:
    """Tests for LocalStorageBackend.setup() method."""
    
    def test_setup_creates_project_directory(self, clean_datamole_dir, tmp_path):
        """Test that setup creates project directory."""
        storage_path = tmp_path / "storage"
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path=str(storage_path))
        global_config.save()
        
        loaded_config = GlobalConfig.load()
        backend_config = loaded_config.get_backend_config(BackendType.LOCAL)
        backend = create_storage_backend(BackendType.LOCAL, backend_config)
        backend.setup("test_project")
        
        project_path = storage_path / "test_project"
        assert project_path.exists()
        assert project_path.is_dir()
    
    def test_setup_verifies_write_access(self, clean_datamole_dir, tmp_path):
        """Test that setup verifies write access."""
        storage_path = tmp_path / "storage"
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path=str(storage_path))
        global_config.save()
        
        loaded_config = GlobalConfig.load()
        backend_config = loaded_config.get_backend_config(BackendType.LOCAL)
        backend = create_storage_backend(BackendType.LOCAL, backend_config)
        
        # Should not raise error
        backend.setup("test_project")
    
    def test_setup_idempotent(self, clean_datamole_dir, tmp_path):
        """Test that setup can be called multiple times."""
        storage_path = tmp_path / "storage"
        global_config = GlobalConfig.initialize_defaults()
        global_config.set_backend_config(BackendType.LOCAL, storage_path=str(storage_path))
        global_config.save()
        
        loaded_config = GlobalConfig.load()
        backend_config = loaded_config.get_backend_config(BackendType.LOCAL)
        backend = create_storage_backend(BackendType.LOCAL, backend_config)
        
        # Call setup twice
        backend.setup("test_project")
        backend.setup("test_project")  # Should not raise error
        
        project_path = storage_path / "test_project"
        assert project_path.exists()
