"""
Tests for add_version() functionality.
"""

import pytest
import os

from datamole.core import DataMole
from datamole.config.project import ProjectConfig
from datamole.storage import (
    BackendType,
    StorageError
)
from datamole.config.global_config import GlobalConfig


@pytest.fixture
def temp_project(tmp_path, temp_home):
    """Create a temporary project directory."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Change to project directory
    original_dir = os.getcwd()
    os.chdir(project_dir)
    
    yield project_dir
    
    # Restore original directory
    os.chdir(original_dir)


@pytest.fixture
def initialized_project(temp_project, temp_home):
    """Create an initialized datamole project."""
    # Set up global config with local backend
    storage_path = temp_home / "datamole_storage"
    global_config = GlobalConfig.initialize_defaults()
    global_config.set_backend_config(BackendType.LOCAL, storage_path=str(storage_path))
    global_config.save()
    
    # Initialize project
    dtm = DataMole()
    dtm.init(data_dir="data", backend="local")
    
    yield dtm, temp_project, storage_path


@pytest.fixture
def project_with_data(initialized_project):
    """Create a project with data in the data directory."""
    dtm, project_dir, storage_path = initialized_project
    
    # Create data directory with files
    data_dir = project_dir / "data"
    data_dir.mkdir(exist_ok=True)
    
    (data_dir / "file1.txt").write_text("content1")
    (data_dir / "file2.txt").write_text("content2")
    
    # Create subdirectory
    subdir = data_dir / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("content3")
    
    yield dtm, project_dir, storage_path, data_dir


class TestAddVersionValidation:
    """Tests for add_version() input validation."""
    
    def test_add_version_without_init(self, temp_project):
        """Test that add_version fails if not initialized."""
        dtm = DataMole()
        
        with pytest.raises(RuntimeError, match="No .datamole file found"):
            dtm.add_version()
    
    def test_add_version_data_directory_not_exists(self, initialized_project):
        """Test that add_version fails if data directory doesn't exist."""
        dtm, project_dir, _ = initialized_project
        
        # Data directory doesn't exist yet
        with pytest.raises(RuntimeError, match="Data directory does not exist"):
            dtm.add_version()
    
    def test_add_version_empty_directory(self, initialized_project):
        """Test that add_version fails if data directory is empty."""
        dtm, project_dir, _ = initialized_project
        
        # Create empty data directory
        data_dir = project_dir / "data"
        data_dir.mkdir()
        
        with pytest.raises(ValueError, match="Data directory is empty"):
            dtm.add_version()


class TestAddVersionSuccess:
    """Tests for successful add_version() execution."""
    
    def test_add_version_creates_version(self, project_with_data):
        """Test that add_version creates a new version."""
        dtm, project_dir, storage_path, data_dir = project_with_data
        
        # Add version
        dtm.add_version(message="Initial version")
        
        # Verify .datamole was updated
        config = ProjectConfig.load(project_dir / ".datamole")
        
        assert len(config.versions) == 1
        assert config.current_version is not None
        assert config.current_version == config.versions[0]["hash"]
        assert config.versions[0]["message"] == "Initial version"
        assert "timestamp" in config.versions[0]
    
    def test_add_version_generates_8_char_hash(self, project_with_data):
        """Test that version hash is 8 characters."""
        dtm, project_dir, storage_path, data_dir = project_with_data
        
        dtm.add_version()
        
        config = ProjectConfig.load(project_dir / ".datamole")
        version_hash = config.versions[0]["hash"]
        
        assert len(version_hash) == 8
        assert all(c in "0123456789abcdef" for c in version_hash)
    
    def test_add_version_uploads_to_storage(self, project_with_data):
        """Test that add_version uploads data to remote storage."""
        dtm, project_dir, storage_path, data_dir = project_with_data
        
        dtm.add_version()
        
        # Get version hash
        config = ProjectConfig.load(project_dir / ".datamole")
        version_hash = config.versions[0]["hash"]
        
        # Verify files exist in storage
        remote_path = storage_path / config.project / version_hash
        assert remote_path.exists()
        assert (remote_path / "file1.txt").read_text() == "content1"
        assert (remote_path / "file2.txt").read_text() == "content2"
        assert (remote_path / "subdir" / "file3.txt").read_text() == "content3"
    
    def test_add_version_without_message(self, project_with_data):
        """Test that add_version works without message."""
        dtm, project_dir, storage_path, data_dir = project_with_data
        
        dtm.add_version()
        
        config = ProjectConfig.load(project_dir / ".datamole")
        
        # Message should not be in version entry if not provided
        assert "message" not in config.versions[0] or config.versions[0]["message"] is None
    
    def test_add_version_updates_current_version(self, project_with_data):
        """Test that add_version updates current_version."""
        dtm, project_dir, storage_path, data_dir = project_with_data
        
        # Add first version
        dtm.add_version(message="Version 1")
        config1 = ProjectConfig.load(project_dir / ".datamole")
        hash1 = config1.current_version
        
        # Modify data
        (data_dir / "new_file.txt").write_text("new content")
        
        # Add second version
        dtm.add_version(message="Version 2")
        config2 = ProjectConfig.load(project_dir / ".datamole")
        hash2 = config2.current_version
        
        # Verify both versions exist
        assert len(config2.versions) == 2
        # Verify current_version is the latest
        assert hash2 != hash1
        assert config2.current_version == hash2
        assert config2.versions[-1]["hash"] == hash2


class TestAddVersionTransactionSafety:
    """Tests for transaction safety in add_version()."""
    
    def test_add_version_failed_upload_does_not_modify_datamole(self, initialized_project, monkeypatch):
        """Test that if upload fails, .datamole is not modified."""
        dtm, project_dir, storage_path = initialized_project
        
        # Create data
        data_dir = project_dir / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("content")
        
        # Load initial config
        initial_config = ProjectConfig.load(project_dir / ".datamole")
        initial_versions = initial_config.versions.copy()
        initial_current = initial_config.current_version
        
        # Mock upload_directory to fail
        from datamole.storage import LocalStorageBackend
        original_upload = LocalStorageBackend.upload_directory
        
        def failing_upload(self, local_path, remote_path):
            raise StorageError("Simulated upload failure")
        
        monkeypatch.setattr(LocalStorageBackend, "upload_directory", failing_upload)
        
        # Try to add version (should fail)
        with pytest.raises(RuntimeError, match="Failed to upload data"):
            dtm.add_version(message="This should fail")
        
        # Verify .datamole was NOT modified
        final_config = ProjectConfig.load(project_dir / ".datamole")
        assert final_config.versions == initial_versions
        assert final_config.current_version == initial_current
        
        # Restore original method
        monkeypatch.setattr(LocalStorageBackend, "upload_directory", original_upload)


class TestAddVersionHashCollision:
    """Tests for hash collision handling."""
    
    def test_add_version_handles_hash_collision(self, project_with_data, monkeypatch):
        """Test that hash collision is handled by generating new hash."""
        dtm, project_dir, storage_path, data_dir = project_with_data
        
        # Add first version to get a hash
        dtm.add_version()
        config = ProjectConfig.load(project_dir / ".datamole")
        existing_hash = config.versions[0]["hash"]
        
        # Mock secrets.token_hex to return existing hash first, then different hash
        import secrets
        call_count = [0]
        
        def mock_token_hex(n):
            call_count[0] += 1
            if call_count[0] == 1:
                return existing_hash  # Collision
            else:
                return "abcd1234"  # New unique hash
        
        monkeypatch.setattr(secrets, "token_hex", mock_token_hex)
        
        # Modify data and add second version
        (data_dir / "new_file.txt").write_text("new")
        dtm.add_version()
        
        # Verify second version has different hash
        config = ProjectConfig.load(project_dir / ".datamole")
        assert len(config.versions) == 2
        assert config.versions[1]["hash"] != existing_hash
        assert call_count[0] >= 2  # Called at least twice due to collision


class TestAddVersionMultipleVersions:
    """Tests for adding multiple versions."""
    
    def test_add_multiple_versions(self, project_with_data):
        """Test adding multiple versions sequentially."""
        dtm, project_dir, storage_path, data_dir = project_with_data
        
        # Add 3 versions with different data
        for i in range(3):
            (data_dir / f"file_{i}.txt").write_text(f"content_{i}")
            dtm.add_version(message=f"Version {i+1}")
        
        # Verify all versions are tracked
        config = ProjectConfig.load(project_dir / ".datamole")
        assert len(config.versions) == 3
        
        # Verify each version has unique hash
        hashes = [v["hash"] for v in config.versions]
        assert len(hashes) == len(set(hashes))  # All unique
        
        # Verify current_version is the latest
        assert config.current_version == config.versions[-1]["hash"]
        
        # Verify all versions exist in storage
        for version in config.versions:
            version_path = storage_path / config.project / version["hash"]
            assert version_path.exists()
