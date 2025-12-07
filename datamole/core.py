"""
Main logic for datamole core functions. Provides the DataMole class API.
"""

import os
import getpass
import secrets
from datetime import datetime
from pathlib import Path
import yaml
from typing import Optional

from datamole.config import DataMoleFileConfig
from datamole.storage import BackendType


class DataMole:
    def __init__(self, config_path=None):
        """
        Initialize a DataMole instance.
        Loads config, sets user, remote, and state.
        """
        self.user = getpass.getuser()
        self.config_path = config_path or os.path.join(os.getcwd(), ".config")
        self.remote_uri = None
        self.auth_token = None
        self.project_name = os.path.basename(os.getcwd())
        self.datamole_file = os.path.join(os.getcwd(), ".datamole")
        self._config = None  # Lazy-loaded DataMoleFileConfig
        self._load_config()

    def _load_config(self):
        """Load config from .config file if present."""
        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
                for line in f:
                    if line.strip() and not line.strip().startswith('#'):
                        if '=' in line:
                            k, v = line.strip().split('=', 1)
                            if k.strip() == 'remote_uri':
                                self.remote_uri = v.strip()
                            elif k.strip() == 'auth_token':
                                self.auth_token = v.strip()
    
    @property
    def config(self) -> DataMoleFileConfig:
        """Lazy-load and return the DataMoleFileConfig instance."""
        if self._config is None:
            if not os.path.exists(self.datamole_file):
                raise RuntimeError("No .datamole file found. Run 'dtm init' first.")
            self._config = DataMoleFileConfig.load(self.datamole_file)
        return self._config

    def init(self, data_dir: str = "data", no_pull: bool = False,
             backend: str = "local") -> None:
        """Initialize datamole in a repo.
        
        Args:
            data_dir: Relative path to data directory (default: "data")
            no_pull: If True, skip auto-downloading when .datamole exists
            backend: Storage backend type (default: "local")
                    Backend must be configured in ~/.datamole/config.yaml
                    Use 'dtm config --backend <type>' to configure backends
        
        Case A: Fresh initialization (no .datamole exists)
            - Creates new .datamole file with data_dir and backend_type
            - Loads backend config from ~/.datamole/config.yaml
            - Calls backend.setup(project_name) to initialize storage
        
        Case B: Existing .datamole (collaborator scenario)
            - Loads existing config (backend parameter ignored)
            - Verifies backend is accessible via backend.setup()
            - Auto-downloads current_version unless no_pull=True
        """
        from datamole.storage import (
            create_storage_backend, 
            BackendType, 
            StorageError,
            initialize_default_config
        )
        
        # Ensure global config exists
        initialize_default_config()
        # Case B: Existing .datamole file
        if os.path.exists(self.datamole_file):
            print(f"Found existing .datamole file for project '{self.project_name}'.")
            
            # Load the config
            self._config = DataMoleFileConfig.load(self.datamole_file)
            
            if not self._config.backend_type:
                raise ValueError(".datamole file missing backend_type. File may be corrupted.")
            
            # Verify backend is configured and accessible
            try:
                backend_enum = BackendType.from_string(self._config.backend_type)
                storage_backend = create_storage_backend(backend_enum)
                storage_backend.setup(self.project_name)
                print(f"Using {self._config.backend_type} backend.")
            except StorageError as e:
                print(f"Error: {e}")
                print(f"Configure backend with: dtm config --backend {self._config.backend_type}")
                raise
            
            # Auto-pull current version unless disabled
            if not no_pull and self._config.current_version:
                print(f"Auto-downloading current version: {self._config.current_version}")
                try:
                    self.pull(self._config.current_version)
                except Exception as e:
                    print(f"Warning: Could not auto-download version: {e}")
            elif not self._config.current_version:
                print("No current version set. Use 'dtm pull <hash>' to download a version.")
            else:
                print("Auto-pull disabled. Use 'dtm pull' to download data.")

            return

        # Case A: Fresh initialization
        print(f"Initializing datamole for project '{self.project_name}'...")
        
        # Validate and load backend
        try:
            backend_enum = BackendType.from_string(backend)
            storage_backend = create_storage_backend(backend_enum)
        except (ValueError, StorageError) as e:
            print(f"Error: {e}")
            print(f"Configure backend with: dtm config --backend {backend}")
            raise
        
        # Set up storage for this project
        try:
            storage_backend.setup(self.project_name)
            print(f"Initialized {backend} backend for project.")
        except StorageError as e:
            print(f"Error setting up storage: {e}")
            raise
        
        # Create .datamole file
        self._config = DataMoleFileConfig.create(
            file_path=self.datamole_file,
            project=self.project_name,
            data_directory=data_dir,
            backend_type=backend
        )
        
        print("Created .datamole file with:")
        print(f"  - data_directory: {data_dir}")
        print(f"  - backend_type: {backend}")
        
        print(f"\nData will be tracked in: {data_dir}/")
        print("\nNext steps:")
        print(f"  1. Add your data to {data_dir}/")
        print("  2. Run 'dtm add-version' to create first version")

    def config_backend(self, backend: str, remote_uri: str, 
                      credentials_path: Optional[str] = None) -> None:
        """Configure a storage backend in global config.
        
        Args:
            backend: Storage backend type ("local", "gcs", "s3", "azure")
            remote_uri: Remote storage URI (backend-specific format)
            credentials_path: Optional path to credentials file
        
        Saves configuration to ~/.datamole/config.yaml
        This config is used by all projects using this backend type.
        """
        from datamole.storage import BackendType, save_backend_config
        
        try:
            backend_enum = BackendType.from_string(backend)
        except ValueError as e:
            print(f"Error: {e}")
            return
        
        # Save to global config
        save_backend_config(backend_enum, remote_uri, credentials_path)
        
        print(f"Configured {backend} backend in ~/.datamole/config.yaml:")
        print(f"  - remote_uri: {remote_uri}")
        if credentials_path:
            print(f"  - credentials_path: {credentials_path}")
        print("\nThis backend can now be used across all datamole projects.")

    def add_version(self, message: Optional[str] = None, tag: Optional[str] = None):
        """Create and track a new version.
        
        This method:
        1. Validates that data_directory exists and is not empty
        2. Validates tag if provided (must be unique)
        3. Generates a random 8-character hex hash for the version
        4. Uploads the data directory to remote storage
        5. Only updates .datamole if upload succeeds (transaction safety)
        6. Sets current_version to the new version
        
        Args:
            message: Optional description for this version
            tag: Optional tag for easy lookup (e.g., "v1.0", "baseline")
                 Must be unique, alphanumeric with .-_ allowed
            
        Raises:
            RuntimeError: If not initialized or data_directory doesn't exist
            ValueError: If data_directory is empty or tag is invalid/duplicate
            StorageError: If upload fails
        """
        from datamole.storage import create_storage_backend, StorageError
        
        # Ensure we're initialized
        config = self.config
        
        if not config.data_directory:
            raise RuntimeError("No data_directory configured. Run 'dtm init' first.")
        
        if not config.backend_type:
            raise RuntimeError("No backend_type configured. File may be corrupted.")
        
        # Get absolute path to data directory
        data_path = Path(config.get_absolute_data_path())
        
        # Validate data directory exists
        if not data_path.exists():
            raise RuntimeError(
                f"Data directory does not exist: {data_path}\n"
                f"Create the directory and add your data before running add_version."
            )
        
        # Validate data directory is not empty
        if not any(data_path.iterdir()):
            raise ValueError(
                f"Data directory is empty: {data_path}\n"
                f"Add some data before creating a version."
            )
        
        print(f"Creating new version from: {config.data_directory}")
        
        # Generate random hash (8-character hex = 4 bytes)
        # Check for collision (extremely unlikely but safe)
        max_attempts = 10
        version_hash = None
        for _ in range(max_attempts):
            candidate_hash = secrets.token_hex(4)  # 4 bytes = 8 hex chars
            if not config.has_version(candidate_hash):
                version_hash = candidate_hash
                break
        
        if not version_hash:
            raise RuntimeError("Failed to generate unique version hash after multiple attempts")
        
        print(f"Generated version hash: {version_hash}")
        
        # Get timestamp
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Load storage backend
        try:
            backend_enum = BackendType.from_string(config.backend_type)
            storage_backend = create_storage_backend(backend_enum)
        except (ValueError, StorageError) as e:
            raise RuntimeError(f"Failed to load storage backend: {e}") from e
        
        # Prepare remote path: project/hash
        remote_path = f"{config.project}/{version_hash}"
        
        # Upload to remote storage (this is the critical operation)
        # TODO: For large directories (>1GB), consider background upload with progress
        print(f"Uploading to {config.backend_type} storage...")
        try:
            storage_backend.upload_directory(data_path, remote_path)
            print("Upload complete.")
        except StorageError as e:
            # Upload failed - do NOT modify .datamole
            raise RuntimeError(
                f"Failed to upload data to remote storage: {e}\n"
                f"Version was NOT created. .datamole file unchanged."
            ) from e
        
        # Upload succeeded - now update .datamole
        config.add_version_entry(version_hash, timestamp, message, tag)
        config.current_version = version_hash
        config.save()
        
        print(f"\n✓ Version {version_hash} created successfully")
        if tag:
            print(f"  Tag: {tag}")
        if message:
            print(f"  Message: {message}")
        print(f"  Timestamp: {timestamp}")
        print(f"  Current version updated to: {version_hash}")

    def list_versions(self):
        """Show all known tracked versions."""
        if not os.path.exists(self.datamole_file):
            print("No .datamole file found.")
            return
        with open(self.datamole_file) as f:
            meta = yaml.safe_load(f)
        for v in meta.get("versions", []):
            print(v)

    def pull(self, version: Optional[str] = None, force: bool = False):
        """Pull a version from remote storage to data_directory.
        
        Lookup priority:
        1. None or "latest" → current_version from .datamole
        2. Exact hash match (8 hex chars)
        3. Hash prefix match (min 4 chars, must be unique)
        4. Tag match (case-sensitive)
        
        Args:
            version: Version identifier (hash, prefix, tag, or None/"latest")
            force: If True, overwrite data directory without confirmation
            
        Raises:
            RuntimeError: If not initialized or version not found
            ValueError: If hash prefix matches multiple versions
            StorageError: If download fails
        """
        from datamole.storage import create_storage_backend, StorageError
        
        # Ensure we're initialized
        config = self.config
        
        if not config.data_directory:
            raise RuntimeError("No data_directory configured. Run 'dtm init' first.")
        
        if not config.backend_type:
            raise RuntimeError("No backend_type configured. File may be corrupted.")
        
        # Determine which version to pull
        version_info = None
        version_hash = None
        lookup_method = None
        
        if version is None or version == "latest":
            # Use current_version
            if not config.current_version:
                raise RuntimeError("No current_version set. Specify a version to pull.")
            version_hash = config.current_version
            version_info = config.get_version_info(version_hash)
            lookup_method = "current version"
        else:
            # Try exact hash match first
            version_info = config.get_version_info(version)
            if version_info:
                version_hash = version
                lookup_method = "hash"
            # Try hash prefix match (if looks like hex and >= 4 chars)
            elif len(version) >= 4 and all(c in "0123456789abcdef" for c in version.lower()):
                matches = config.get_versions_by_hash_prefix(version.lower())
                if len(matches) == 0:
                    pass  # Will try tag lookup next
                elif len(matches) == 1:
                    version_info = matches[0]
                    version_hash = version_info["hash"]
                    lookup_method = f"hash prefix '{version}'"
                else:
                    # Multiple matches - ambiguous
                    hash_list = ", ".join(v["hash"] for v in matches)
                    raise ValueError(
                        f"Hash prefix '{version}' matches multiple versions: {hash_list}\n"
                        f"Please use a more specific prefix or full hash."
                    )
            # Try tag lookup
            if not version_info:
                version_info = config.get_version_by_tag(version)
                if version_info:
                    version_hash = version_info["hash"]
                    lookup_method = f"tag '{version}'"
        
        # Version not found
        if not version_info or not version_hash:
            raise RuntimeError(
                f"Version '{version}' not found.\n"
                f"Use 'dtm list-versions' to see available versions."
            )
        
        print(f"Pulling version {version_hash} ({lookup_method})")
        if version_info.get("tag"):
            print(f"  Tag: {version_info['tag']}")
        if version_info.get("message"):
            print(f"  Message: {version_info['message']}")
        
        # Get absolute path to data directory
        data_path = Path(config.get_absolute_data_path())
        
        # Check if data directory exists and has content
        if data_path.exists() and any(data_path.iterdir()):
            if not force:
                response = input(f"\nData directory '{config.data_directory}' is not empty. Overwrite? [y/N]: ")
                if response.lower() != 'y':
                    print("Pull cancelled.")
                    return
            print(f"Overwriting existing data in {config.data_directory}")
        
        # Load storage backend
        try:
            backend_enum = BackendType.from_string(config.backend_type)
            storage_backend = create_storage_backend(backend_enum)
        except (ValueError, StorageError) as e:
            raise RuntimeError(f"Failed to load storage backend: {e}") from e
        
        # Prepare remote path: project/hash
        remote_path = f"{config.project}/{version_hash}"
        
        # Download from remote storage
        print(f"Downloading from {config.backend_type} storage...")
        try:
            storage_backend.download_directory(remote_path, data_path)
            print("Download complete.")
        except StorageError as e:
            raise RuntimeError(
                f"Failed to download data from remote storage: {e}\n"
                f"Version: {version_hash}"
            ) from e
        
        print(f"\n✓ Successfully pulled version {version_hash} to {config.data_directory}")

    def show_current_version(self):
        """Display the current active version."""
        config = self.config
        
        if not config.current_version:
            print("No current version set.")
            return
        
        version_info = config.get_version_info(config.current_version)
        if not version_info:
            print(f"Current version: {config.current_version} (not found in history)")
            return
        
        print(f"Current version: {config.current_version}")
        if version_info.get("tag"):
            print(f"  Tag: {version_info['tag']}")
        if version_info.get("message"):
            print(f"  Message: {version_info['message']}")
        print(f"  Timestamp: {version_info['timestamp']}")

    def delete_version(self, version_hash):
        """Delete a version (with permissions check)."""
        print(f"Deleting version {version_hash} (not implemented)")
