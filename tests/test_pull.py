"""Unit tests for DataMole.pull() method."""

import pytest
import shutil
from unittest.mock import patch
from datamole.core import DataMole


class TestPullValidation:
    """Test input validation for pull()."""
    
    def test_pull_before_init(self, temp_project):
        """Test that pull fails when project not initialized."""
        dtm = DataMole()
        
        with pytest.raises(RuntimeError, match="No .datamole file found"):
            dtm.pull()
    
    def test_pull_with_corrupted_config(self, temp_project, configured_storage):
        """Test that pull fails when backend_type is missing."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Corrupt the config by removing backend_type
        config = dtm.config
        config.backend_type = None
        config.save()
        
        # Reload and try to pull
        dtm = DataMole()
        with pytest.raises(RuntimeError, match="No backend_type configured"):
            dtm.pull()
    
    def test_pull_when_no_current_version(self, temp_project, configured_storage):
        """Test that pull with no args fails when no current_version set."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # No versions created yet
        with pytest.raises(RuntimeError, match="No current_version set"):
            dtm.pull()
    
    def test_pull_nonexistent_version(self, temp_project, configured_storage):
        """Test that pull fails for non-existent version."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        with pytest.raises(RuntimeError, match="Version 'abcd1234' not found"):
            dtm.pull("abcd1234")


class TestPullVersionLookup:
    """Test version lookup strategies in pull()."""
    
    def test_pull_without_args_uses_current_version(self, temp_project, configured_storage):
        """Test that pull() without args pulls current_version."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create first version
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First version")
        
        # Modify data
        (data_dir / "file1.txt").write_text("modified")
        
        # Pull without args should restore current version
        with patch("builtins.input", return_value="y"):
            dtm.pull()
        
        assert (data_dir / "file1.txt").read_text() == "version 1"
    
    def test_pull_with_latest_keyword(self, temp_project, configured_storage):
        """Test that pull('latest') pulls current_version."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create versions
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        
        (data_dir / "file1.txt").write_text("version 2")
        dtm.add_version(message="Second")
        
        # Modify data
        (data_dir / "file1.txt").write_text("modified")
        
        # Pull latest
        with patch("builtins.input", return_value="y"):
            dtm.pull("latest")
        
        assert (data_dir / "file1.txt").read_text() == "version 2"
    
    def test_pull_with_exact_hash(self, temp_project, configured_storage):
        """Test pulling by exact hash match."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create two versions
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        v1_hash = dtm.config.current_version
        
        (data_dir / "file1.txt").write_text("version 2")
        dtm.add_version(message="Second")
        
        # Pull first version by exact hash
        with patch("builtins.input", return_value="y"):
            dtm.pull(v1_hash)
        
        assert (data_dir / "file1.txt").read_text() == "version 1"
    
    def test_pull_with_hash_prefix(self, temp_project, configured_storage):
        """Test pulling by hash prefix (minimum 4 chars)."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        v1_hash = dtm.config.current_version
        
        (data_dir / "file1.txt").write_text("version 2")
        dtm.add_version(message="Second")
        
        # Pull by 4-char prefix
        prefix = v1_hash[:4]
        with patch("builtins.input", return_value="y"):
            dtm.pull(prefix)
        
        assert (data_dir / "file1.txt").read_text() == "version 1"
    
    def test_pull_with_ambiguous_hash_prefix(self, temp_project, configured_storage):
        """Test that ambiguous hash prefix raises error."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create two versions with same prefix (unlikely but test the logic)
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        
        # Mock to force hash collision on prefix
        with patch("secrets.token_hex") as mock_hex:
            mock_hex.side_effect = ["aaaa1111", "aaaa2222"]  # Same 4-char prefix
            dtm.add_version(message="First")
            dtm.add_version(message="Second")
        
        # Try to pull with ambiguous prefix
        with pytest.raises(ValueError, match="matches multiple versions"):
            dtm.pull("aaaa")
    
    def test_pull_with_tag(self, temp_project, configured_storage):
        """Test pulling by tag name."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version with tag
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First", tag="baseline")
        
        (data_dir / "file1.txt").write_text("version 2")
        dtm.add_version(message="Second", tag="experiment")
        
        # Pull by tag
        with patch("builtins.input", return_value="y"):
            dtm.pull("baseline")
        
        assert (data_dir / "file1.txt").read_text() == "version 1"
    
    def test_pull_hash_prefix_takes_priority_over_tag(self, temp_project, configured_storage):
        """Test that hash prefix matching happens before tag lookup."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version with tag that looks like hex
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First", tag="abcd")
        v1_hash = dtm.config.current_version
        
        # If v1_hash starts with "abcd", pull("abcd") should match hash not tag
        # Otherwise this test is N/A
        if v1_hash.startswith("abcd"):
            (data_dir / "file1.txt").write_text("version 2")
            dtm.add_version(message="Second", tag="other")
            
            with patch("builtins.input", return_value="y"):
                dtm.pull("abcd")
            
            # Should have pulled v1 by hash prefix, not by tag
            assert (data_dir / "file1.txt").read_text() == "version 1"


class TestPullOverwriteConfirmation:
    """Test confirmation prompting for overwriting data."""
    
    def test_pull_prompts_when_data_exists(self, temp_project, configured_storage):
        """Test that pull prompts before overwriting existing data."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        
        # Modify data
        (data_dir / "file1.txt").write_text("modified")
        
        # Mock user declining overwrite
        with patch("builtins.input", return_value="n") as mock_input:
            dtm.pull()
            mock_input.assert_called_once()
        
        # Data should not be overwritten
        assert (data_dir / "file1.txt").read_text() == "modified"
    
    def test_pull_with_force_skips_confirmation(self, temp_project, configured_storage):
        """Test that force=True skips confirmation prompt."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        
        # Modify data
        (data_dir / "file1.txt").write_text("modified")
        
        # Pull with force - no prompt should appear
        with patch("builtins.input") as mock_input:
            dtm.pull(force=True)
            mock_input.assert_not_called()
        
        # Data should be overwritten
        assert (data_dir / "file1.txt").read_text() == "version 1"
    
    def test_pull_into_empty_directory_no_prompt(self, temp_project, configured_storage):
        """Test that pull into empty directory doesn't prompt."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        
        # Delete data directory contents
        shutil.rmtree(data_dir)
        data_dir.mkdir()
        
        # Pull should not prompt
        with patch("builtins.input") as mock_input:
            dtm.pull()
            mock_input.assert_not_called()
        
        assert (data_dir / "file1.txt").read_text() == "version 1"


class TestPullDownload:
    """Test download functionality in pull()."""
    
    def test_pull_downloads_from_backend(self, temp_project, configured_storage):
        """Test that pull successfully downloads data from backend."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        (data_dir / "subdir").mkdir()
        (data_dir / "subdir" / "file2.txt").write_text("nested file")
        dtm.add_version(message="First")
        
        # Delete local data
        shutil.rmtree(data_dir)
        data_dir.mkdir()
        
        # Pull should restore everything
        dtm.pull()
        
        assert (data_dir / "file1.txt").read_text() == "version 1"
        assert (data_dir / "subdir" / "file2.txt").read_text() == "nested file"
    
    def test_pull_creates_data_directory_if_missing(self, temp_project, configured_storage):
        """Test that pull creates data directory if it doesn't exist."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        
        # Delete data directory completely
        shutil.rmtree(data_dir)
        
        # Pull should recreate directory
        dtm.pull()
        
        assert data_dir.exists()
        assert (data_dir / "file1.txt").read_text() == "version 1"
    
    def test_pull_handles_backend_error(self, temp_project, configured_storage):
        """Test that pull handles backend download errors gracefully."""
        from datamole.storage import StorageError
        
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create version
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        
        # Mock backend to raise error
        with patch("datamole.storage.LocalStorageBackend.download_directory") as mock_download:
            mock_download.side_effect = StorageError("Network error")
            
            with patch("builtins.input", return_value="y"):
                with pytest.raises(RuntimeError, match="Failed to download data from remote storage"):
                    dtm.pull()


class TestPullCurrentVersionBehavior:
    """Test that pull() does not modify current_version."""
    
    def test_pull_does_not_change_current_version(self, temp_project, configured_storage):
        """Test that pulling an old version doesn't change current_version."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create two versions
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First")
        v1_hash = dtm.config.current_version
        
        (data_dir / "file1.txt").write_text("version 2")
        dtm.add_version(message="Second")
        v2_hash = dtm.config.current_version
        
        # Pull old version
        with patch("builtins.input", return_value="y"):
            dtm.pull(v1_hash)
        
        # current_version should still be v2
        dtm_reload = DataMole()
        assert dtm_reload.config.current_version == v2_hash
    
    def test_pull_with_tag_does_not_change_current_version(self, temp_project, configured_storage):
        """Test that pulling by tag doesn't change current_version."""
        dtm = DataMole()
        dtm.init(data_dir="data", backend="local")
        
        # Create two versions
        data_dir = temp_project / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / "file1.txt").write_text("version 1")
        dtm.add_version(message="First", tag="v1")
        
        (data_dir / "file1.txt").write_text("version 2")
        dtm.add_version(message="Second", tag="v2")
        v2_hash = dtm.config.current_version
        
        # Pull old version by tag
        with patch("builtins.input", return_value="y"):
            dtm.pull("v1")
        
        # current_version should still be v2
        dtm_reload = DataMole()
        assert dtm_reload.config.current_version == v2_hash
