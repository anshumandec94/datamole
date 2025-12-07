"""
Integration tests for complete datamole workflows.

These tests verify end-to-end functionality across multiple components.
"""

import pytest
import os
import shutil
from pathlib import Path
import yaml

from datamole.core import DataMole
from datamole.config import DataMoleFileConfig
from datamole.storage import (
    BackendType,
    save_backend_config,
    create_storage_backend,
)


class TestDataOwnerWorkflow:
    """Test the complete workflow for a data owner creating versions."""
    
    def test_complete_data_owner_workflow(self, temp_project, configured_storage):
        """
        Test complete workflow:
        1. Initialize project
        2. Add data
        3. Create version
        4. Verify .datamole
        5. Verify remote storage
        """
        # Step 1: Initialize project
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Verify .datamole was created
        datamole_path = temp_project / ".datamole"
        assert datamole_path.exists()
        
        config = DataMoleFileConfig.load(datamole_path)
        assert config.project == "test_project"
        assert config.data_directory == "data"
        assert config.backend_type == "local"
        assert config.current_version is None
        assert len(config.versions) == 0
        
        # Step 2: Add data
        data_dir = temp_project / "data"
        data_dir.mkdir()
        
        (data_dir / "train.csv").write_text("id,value\n1,100\n2,200\n")
        (data_dir / "test.csv").write_text("id,value\n3,300\n")
        
        models_dir = data_dir / "models"
        models_dir.mkdir()
        (models_dir / "model.pkl").write_text("model_data")
        
        # Step 3: Create first version
        dtm.add_version(message="Initial dataset")
        
        # Step 4: Verify .datamole was updated
        config = DataMoleFileConfig.load(datamole_path)
        assert len(config.versions) == 1
        assert config.current_version is not None
        
        version1_hash = config.versions[0]["hash"]
        assert config.current_version == version1_hash
        assert config.versions[0]["message"] == "Initial dataset"
        assert "timestamp" in config.versions[0]
        
        # Step 5: Verify data exists in remote storage
        remote_path = configured_storage / "test_project" / version1_hash
        assert remote_path.exists()
        assert (remote_path / "train.csv").exists()
        assert (remote_path / "test.csv").exists()
        assert (remote_path / "models" / "model.pkl").exists()
        
        # Verify content matches
        assert (remote_path / "train.csv").read_text() == "id,value\n1,100\n2,200\n"
        
        # Step 6: Modify data and create second version
        (data_dir / "validation.csv").write_text("id,value\n4,400\n")
        dtm.add_version(message="Added validation set")
        
        # Verify second version
        config = DataMoleFileConfig.load(datamole_path)
        assert len(config.versions) == 2
        
        version2_hash = config.versions[1]["hash"]
        assert config.current_version == version2_hash
        assert version2_hash != version1_hash
        
        # Verify second version in storage
        remote_path2 = configured_storage / "test_project" / version2_hash
        assert remote_path2.exists()
        assert (remote_path2 / "validation.csv").exists()
        
        # Verify first version still exists
        assert (configured_storage / "test_project" / version1_hash).exists()


class TestCollaboratorWorkflow:
    """Test the workflow for a collaborator pulling existing project."""
    
    def test_collaborator_init_pulls_current_version(self, temp_home, tmp_path):
        """
        Test collaborator workflow:
        1. Data owner creates project and version
        2. Collaborator clones repo (simulated)
        3. Collaborator runs init (should auto-pull)
        4. Verify data directory is populated
        """
        # Setup storage
        storage_path = temp_home / "datamole_storage"
        save_backend_config(BackendType.LOCAL, str(storage_path))
        
        # === Data Owner's Actions ===
        owner_project = tmp_path / "owner_project"
        owner_project.mkdir()
        os.chdir(owner_project)
        
        dtm_owner = DataMole()
        dtm_owner.init(data_dir="data", backend="local")
        
        # Add data
        data_dir = owner_project / "data"
        data_dir.mkdir()
        (data_dir / "dataset.csv").write_text("data here")
        
        # Create version
        dtm_owner.add_version(message="Initial data")
        
        # === Collaborator's Actions ===
        # Simulate git clone (copy .datamole but not data)
        collab_project = tmp_path / "collab_project"
        collab_project.mkdir()
        
        shutil.copy(owner_project / ".datamole", collab_project / ".datamole")
        
        os.chdir(collab_project)
        
        # Verify data directory doesn't exist yet
        assert not (collab_project / "data").exists()
        
        # Initialize (should auto-pull)
        dtm_collab = DataMole()
        dtm_collab.init()
        
        # Verify data was pulled
        assert (collab_project / "data").exists()
        assert (collab_project / "data" / "dataset.csv").exists()
        assert (collab_project / "data" / "dataset.csv").read_text() == "data here"
    
    def test_collaborator_init_with_no_pull_flag(self, temp_home, tmp_path):
        """Test collaborator can skip auto-pull with --no-pull flag."""
        # Setup
        storage_path = temp_home / "datamole_storage"
        save_backend_config(BackendType.LOCAL, str(storage_path))
        
        # Owner creates version
        owner_project = tmp_path / "owner_project"
        owner_project.mkdir()
        os.chdir(owner_project)
        
        dtm_owner = DataMole()
        dtm_owner.init(data_dir="data", backend="local")
        
        data_dir = owner_project / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("content")
        dtm_owner.add_version()
        
        # Collaborator clones
        collab_project = tmp_path / "collab_project"
        collab_project.mkdir()
        shutil.copy(owner_project / ".datamole", collab_project / ".datamole")
        os.chdir(collab_project)
        
        # Init with no_pull=True
        dtm_collab = DataMole()
        dtm_collab.init(no_pull=True)
        
        # Verify data was NOT pulled
        assert not (collab_project / "data").exists()


class TestBackendSwitching:
    """Test switching between different backend configurations."""
    
    def test_project_with_different_backends(self, temp_home, tmp_path):
        """Test that different projects can use different backends."""
        # Configure two different local storage locations
        storage1 = temp_home / "storage1"
        storage2 = temp_home / "storage2"
        
        save_backend_config(BackendType.LOCAL, str(storage1))
        
        # Create project 1
        project1 = tmp_path / "project1"
        project1.mkdir()
        os.chdir(project1)
        
        dtm1 = DataMole()
        dtm1.init(data_dir="data", backend="local")
        
        data_dir1 = project1 / "data"
        data_dir1.mkdir()
        (data_dir1 / "file1.txt").write_text("project1 data")
        dtm1.add_version()
        
        # Verify data in storage1
        config1 = DataMoleFileConfig.load(project1 / ".datamole")
        version1_path = storage1 / config1.project / config1.current_version
        assert version1_path.exists()
        
        # Reconfigure to storage2
        save_backend_config(BackendType.LOCAL, str(storage2))
        
        # Create project 2
        project2 = tmp_path / "project2"
        project2.mkdir()
        os.chdir(project2)
        
        dtm2 = DataMole()
        dtm2.init(data_dir="data", backend="local")
        
        data_dir2 = project2 / "data"
        data_dir2.mkdir()
        (data_dir2 / "file2.txt").write_text("project2 data")
        dtm2.add_version()
        
        # Verify data in storage2
        config2 = DataMoleFileConfig.load(project2 / ".datamole")
        version2_path = storage2 / config2.project / config2.current_version
        assert version2_path.exists()
        
        # Verify data NOT in storage1
        version2_wrong_path = storage1 / config2.project / config2.current_version
        assert not version2_wrong_path.exists()


class TestErrorHandling:
    """Test error handling in integration scenarios."""
    
    def test_init_with_invalid_backend(self, temp_project):
        """Test that init fails gracefully with invalid backend type."""
        dtm = DataMole()
        
        with pytest.raises(ValueError, match="Unsupported backend type"):
            dtm.init(backend="invalid_backend")
    
    def test_add_version_after_deleting_data(self, temp_project, configured_storage):
        """Test error when data directory is deleted after init."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create and then delete data directory
        data_dir = temp_project / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("content")
        shutil.rmtree(data_dir)
        
        with pytest.raises(RuntimeError, match="Data directory does not exist"):
            dtm.add_version()


class TestVersionTracking:
    """Test version tracking and metadata."""
    
    def test_version_metadata_persistence(self, temp_project, configured_storage):
        """Test that version metadata persists correctly."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        data_dir = temp_project / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("v1")
        
        # Add multiple versions with different messages
        messages = ["First version", "Second version", "Third version"]
        for msg in messages:
            dtm.add_version(message=msg)
            (data_dir / "file.txt").write_text(f"updated: {msg}")
        
        # Reload config and verify all metadata
        config = DataMoleFileConfig.load(temp_project / ".datamole")
        
        assert len(config.versions) == 3
        for i, version in enumerate(config.versions):
            assert version["message"] == messages[i]
            assert "hash" in version
            assert "timestamp" in version
            assert len(version["hash"]) == 8
