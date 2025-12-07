"""
Tests for storage backend functionality.
"""

import pytest
import os
import shutil
from pathlib import Path
from datamole.storage import (
    StorageBackend, 
    LocalStorageBackend, 
    StorageError,
    BackendType,
    create_storage_backend,
    save_backend_config
)


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create a temporary storage directory."""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    yield storage_dir
    # Cleanup
    if storage_dir.exists():
        shutil.rmtree(storage_dir)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory with some files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Create some test files
    (data_dir / "file1.txt").write_text("content1")
    (data_dir / "file2.txt").write_text("content2")
    
    # Create subdirectory with files
    subdir = data_dir / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("content3")
    
    yield data_dir


@pytest.fixture
def local_backend(temp_storage_dir):
    """Create a LocalStorageBackend instance."""
    return LocalStorageBackend(str(temp_storage_dir))


class TestLocalStorageBackend:
    """Tests for LocalStorageBackend class."""
    
    def test_init_with_absolute_path(self, temp_storage_dir):
        """Test initialization with absolute path."""
        backend = LocalStorageBackend(str(temp_storage_dir))
        assert backend.base_path == temp_storage_dir
    
    def test_init_with_file_protocol(self, temp_storage_dir):
        """Test initialization with file:// protocol."""
        backend = LocalStorageBackend(f"file://{temp_storage_dir}")
        assert backend.base_path == temp_storage_dir
    
    def test_init_creates_base_directory(self, tmp_path):
        """Test that initialization creates base directory if it doesn't exist."""
        storage_dir = tmp_path / "new_storage"
        assert not storage_dir.exists()
        
        backend = LocalStorageBackend(str(storage_dir))
        assert storage_dir.exists()
        assert backend.base_path == storage_dir
    
    def test_upload_directory_success(self, local_backend, temp_data_dir, temp_storage_dir):
        """Test successful directory upload."""
        remote_path = "test_project/abc123"
        
        local_backend.upload_directory(temp_data_dir, remote_path)
        
        # Verify files were copied
        uploaded_path = temp_storage_dir / "test_project" / "abc123"
        assert uploaded_path.exists()
        assert (uploaded_path / "file1.txt").read_text() == "content1"
        assert (uploaded_path / "file2.txt").read_text() == "content2"
        assert (uploaded_path / "subdir" / "file3.txt").read_text() == "content3"
    
    def test_upload_directory_nonexistent_source(self, local_backend, tmp_path):
        """Test upload with non-existent source directory."""
        nonexistent = tmp_path / "nonexistent"
        
        with pytest.raises(StorageError, match="does not exist"):
            local_backend.upload_directory(nonexistent, "project/hash")
    
    def test_upload_directory_source_is_file(self, local_backend, tmp_path):
        """Test upload when source is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        
        with pytest.raises(StorageError, match="not a directory"):
            local_backend.upload_directory(file_path, "project/hash")
    
    def test_upload_directory_invalid_remote_path(self, local_backend, temp_data_dir):
        """Test upload with invalid remote_path format."""
        with pytest.raises(StorageError, match="Invalid remote_path format"):
            local_backend.upload_directory(temp_data_dir, "invalid")
        
        with pytest.raises(StorageError, match="Invalid remote_path format"):
            local_backend.upload_directory(temp_data_dir, "too/many/parts")
    
    def test_upload_directory_idempotent(self, local_backend, temp_data_dir, temp_storage_dir):
        """Test that uploading same version twice is idempotent."""
        remote_path = "test_project/abc123"
        
        # Upload once
        local_backend.upload_directory(temp_data_dir, remote_path)
        
        # Modify uploaded files
        uploaded_path = temp_storage_dir / "test_project" / "abc123"
        (uploaded_path / "file1.txt").write_text("modified")
        
        # Upload again - should overwrite
        local_backend.upload_directory(temp_data_dir, remote_path)
        
        # Verify original content restored
        assert (uploaded_path / "file1.txt").read_text() == "content1"
    
    def test_download_directory_success(self, local_backend, temp_data_dir, tmp_path):
        """Test successful directory download."""
        remote_path = "test_project/abc123"
        
        # Upload first
        local_backend.upload_directory(temp_data_dir, remote_path)
        
        # Download to new location
        download_path = tmp_path / "downloaded"
        local_backend.download_directory(remote_path, download_path)
        
        # Verify files were copied
        assert download_path.exists()
        assert (download_path / "file1.txt").read_text() == "content1"
        assert (download_path / "file2.txt").read_text() == "content2"
        assert (download_path / "subdir" / "file3.txt").read_text() == "content3"
    
    def test_download_directory_nonexistent_version(self, local_backend, tmp_path):
        """Test download of non-existent version."""
        download_path = tmp_path / "downloaded"
        
        with pytest.raises(StorageError, match="Version not found"):
            local_backend.download_directory("project/nonexistent", download_path)
    
    def test_download_directory_invalid_remote_path(self, local_backend, tmp_path):
        """Test download with invalid remote_path format."""
        download_path = tmp_path / "downloaded"
        
        with pytest.raises(StorageError, match="Invalid remote_path format"):
            local_backend.download_directory("invalid", download_path)
    
    def test_download_directory_overwrites_existing(self, local_backend, temp_data_dir, tmp_path):
        """Test that download overwrites existing directory."""
        remote_path = "test_project/abc123"
        
        # Upload
        local_backend.upload_directory(temp_data_dir, remote_path)
        
        # Create download location with different content
        download_path = tmp_path / "downloaded"
        download_path.mkdir()
        (download_path / "old_file.txt").write_text("old content")
        
        # Download - should overwrite
        local_backend.download_directory(remote_path, download_path)
        
        # Verify old content is gone and new content is present
        assert not (download_path / "old_file.txt").exists()
        assert (download_path / "file1.txt").read_text() == "content1"
    
    def test_list_versions_empty_project(self, local_backend):
        """Test listing versions for project with no versions."""
        versions = local_backend.list_versions("nonexistent_project")
        assert versions == []
    
    def test_list_versions_with_versions(self, local_backend, temp_data_dir):
        """Test listing versions for project with multiple versions."""
        # Upload multiple versions
        local_backend.upload_directory(temp_data_dir, "project/hash1")
        local_backend.upload_directory(temp_data_dir, "project/hash2")
        local_backend.upload_directory(temp_data_dir, "project/hash3")
        
        versions = local_backend.list_versions("project")
        assert len(versions) == 3
        assert set(versions) == {"hash1", "hash2", "hash3"}
    
    def test_version_exists_true(self, local_backend, temp_data_dir):
        """Test version_exists returns True for existing version."""
        local_backend.upload_directory(temp_data_dir, "project/abc123")
        assert local_backend.version_exists("project", "abc123") is True
    
    def test_version_exists_false(self, local_backend):
        """Test version_exists returns False for non-existent version."""
        assert local_backend.version_exists("project", "nonexistent") is False
    
    def test_version_exists_nonexistent_project(self, local_backend):
        """Test version_exists returns False for non-existent project."""
        assert local_backend.version_exists("nonexistent_project", "hash") is False


class TestLocalStorageBackendSetup:
    """Tests for LocalStorageBackend.setup() method."""
    
    def test_setup_creates_project_directory(self, local_backend):
        """Test that setup creates project directory."""
        local_backend.setup("test_project")
        
        project_path = local_backend.base_path / "test_project"
        assert project_path.exists()
        assert project_path.is_dir()
    
    def test_setup_verifies_write_access(self, local_backend):
        """Test that setup verifies write access."""
        # Should not raise error
        local_backend.setup("test_project")
    
    def test_setup_idempotent(self, local_backend):
        """Test that setup can be called multiple times."""
        # Call setup twice
        local_backend.setup("test_project")
        local_backend.setup("test_project")  # Should not raise error
        
        project_path = local_backend.base_path / "test_project"
        assert project_path.exists()
