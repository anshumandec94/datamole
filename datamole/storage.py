"""
Remote storage handling for datamole.

Supports multiple storage backends:
- Local file storage (for testing and simple use cases)
- GCS (Google Cloud Storage)
- S3 (Amazon S3)
- Azure Blob Storage
- Remote file storage (SFTP, etc.)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
import shutil
import os
import yaml


class BackendType(Enum):
    """Enum for supported storage backend types."""
    LOCAL = "local"
    GCS = "gcs"
    S3 = "s3"
    AZURE = "azure"
    
    @classmethod
    def from_string(cls, value: str) -> 'BackendType':
        """Convert string to BackendType enum."""
        value_lower = value.lower()
        for backend in cls:
            if backend.value == value_lower:
                return backend
        raise ValueError(f"Unsupported backend type: {value}. "
                        f"Supported types: {', '.join(b.value for b in cls)}")


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def setup(self, project_name: str) -> None:
        """
        Set up storage for a new project (or verify existing setup).
        
        This is called when a project is first initialized with datamole.
        The backend should:
        - Verify that the remote storage location is accessible
        - Create the project directory structure if needed
        - Validate credentials/permissions
        
        Args:
            project_name: Name of the project to set up
            
        Raises:
            StorageError: If setup fails or remote is not accessible
        """
        pass
    
    @abstractmethod
    def upload_directory(self, local_path: Path, remote_path: str) -> None:
        """
        Upload entire directory to remote storage.
        
        Args:
            local_path: Local directory path to upload
            remote_path: Remote destination path (backend-specific format)
            
        Raises:
            StorageError: If upload fails
        """
        pass
    
    @abstractmethod
    def download_directory(self, remote_path: str, local_path: Path) -> None:
        """
        Download entire directory from remote storage.
        
        Args:
            remote_path: Remote source path (backend-specific format)
            local_path: Local destination directory path
            
        Raises:
            StorageError: If download fails
        """
        pass
    
    @abstractmethod
    def list_versions(self, project_name: str) -> List[str]:
        """
        List all version hashes available in remote storage for a project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            List of version hash strings
        """
        pass
    
    @abstractmethod
    def version_exists(self, project_name: str, version_hash: str) -> bool:
        """
        Check if a version exists in remote storage.
        
        Args:
            project_name: Name of the project
            version_hash: Version hash to check
            
        Returns:
            True if version exists, False otherwise
        """
        pass


class StorageError(Exception):
    """Raised when storage operations fail."""
    pass


class LocalStorageBackend(StorageBackend):
    """
    Local file system storage backend.
    
    Useful for testing and simple use cases where data is stored locally
    or on a mounted network drive.
    
    Remote URI format: file:///absolute/path/to/storage
    or simply: /absolute/path/to/storage
    """
    
    def __init__(self, remote_uri: str):
        """
        Initialize local storage backend.
        
        Args:
            remote_uri: Base path for storage (e.g., "/data/datamole" or "file:///data/datamole")
        """
        # Strip file:// prefix if present
        if remote_uri.startswith("file://"):
            remote_uri = remote_uri[7:]
        
        self.base_path = Path(remote_uri).expanduser().resolve()
        
        # Create base directory if it doesn't exist
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def setup(self, project_name: str) -> None:
        """
        Set up storage for a project.
        
        For local backend, this creates the project directory and verifies write access.
        
        Args:
            project_name: Name of the project
            
        Raises:
            StorageError: If directory cannot be created or is not writable
        """
        project_path = self.base_path / project_name
        
        try:
            # Create project directory if it doesn't exist
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Verify write access by creating and removing a test file
            test_file = project_path / ".datamole_test"
            test_file.touch()
            test_file.unlink()
            
        except PermissionError as e:
            raise StorageError(f"No write permission for storage location: {self.base_path}") from e
        except Exception as e:
            raise StorageError(f"Failed to set up project storage: {e}") from e
    
    def _get_version_path(self, project_name: str, version_hash: str) -> Path:
        """Get the storage path for a specific version."""
        return self.base_path / project_name / version_hash
    
    def upload_directory(self, local_path: Path, remote_path: str) -> None:
        """
        Upload directory by copying to local storage location.
        
        Args:
            local_path: Local directory to upload
            remote_path: Format: "<project_name>/<version_hash>"
        """
        if not local_path.exists():
            raise StorageError(f"Local path does not exist: {local_path}")
        
        if not local_path.is_dir():
            raise StorageError(f"Local path is not a directory: {local_path}")
        
        # Parse remote_path (format: "project/hash")
        parts = remote_path.split("/")
        if len(parts) != 2:
            raise StorageError(f"Invalid remote_path format: {remote_path}. Expected: project_name/version_hash")
        
        project_name, version_hash = parts
        dest_path = self._get_version_path(project_name, version_hash)
        
        # Remove destination if it exists (for idempotency)
        if dest_path.exists():
            shutil.rmtree(dest_path)
        
        # Copy directory tree
        try:
            shutil.copytree(local_path, dest_path)
        except Exception as e:
            raise StorageError(f"Failed to upload directory: {e}") from e
    
    def download_directory(self, remote_path: str, local_path: Path) -> None:
        """
        Download directory by copying from local storage location.
        
        Args:
            remote_path: Format: "<project_name>/<version_hash>"
            local_path: Local destination directory
        """
        # Parse remote_path
        parts = remote_path.split("/")
        if len(parts) != 2:
            raise StorageError(f"Invalid remote_path format: {remote_path}. Expected: project_name/version_hash")
        
        project_name, version_hash = parts
        source_path = self._get_version_path(project_name, version_hash)
        
        if not source_path.exists():
            raise StorageError(f"Version not found in storage: {remote_path}")
        
        # Remove destination if it exists
        if local_path.exists():
            shutil.rmtree(local_path)
        
        # Copy directory tree
        try:
            shutil.copytree(source_path, local_path)
        except Exception as e:
            raise StorageError(f"Failed to download directory: {e}") from e
    
    def list_versions(self, project_name: str) -> List[str]:
        """
        List all version hashes for a project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            List of version hash strings
        """
        project_path = self.base_path / project_name
        
        if not project_path.exists():
            return []
        
        # List all subdirectories (each is a version hash)
        versions = []
        for item in project_path.iterdir():
            if item.is_dir():
                versions.append(item.name)
        
        return versions
    
    def version_exists(self, project_name: str, version_hash: str) -> bool:
        """
        Check if a version exists.
        
        Args:
            project_name: Name of the project
            version_hash: Version hash to check
            
        Returns:
            True if version exists, False otherwise
        """
        version_path = self._get_version_path(project_name, version_hash)
        return version_path.exists() and version_path.is_dir()


def get_datamole_dir() -> Path:
    """Get the datamole configuration directory (~/.datamole)."""
    import os
    home = Path(os.environ.get('HOME', str(Path.home())))
    datamole_dir = home / ".datamole"
    datamole_dir.mkdir(parents=True, exist_ok=True)
    return datamole_dir


def get_config_path() -> Path:
    """Get the path to the global config file."""
    return get_datamole_dir() / "config.yaml"


def load_backend_config(backend_type: BackendType) -> Dict[str, Any]:
    """
    Load backend configuration from global config file.
    
    Args:
        backend_type: Type of backend to load config for
        
    Returns:
        Dict with backend configuration (remote_uri, credentials_path, etc.)
        
    Raises:
        StorageError: If config file doesn't exist or backend not configured
    """
    config_path = get_config_path()
    
    if not config_path.exists():
        raise StorageError(
            f"Global config file not found at {config_path}. "
            f"Run 'dtm config --backend {backend_type.value}' to configure."
        )
    
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    
    backends = config.get("backends", {})
    backend_config = backends.get(backend_type.value)
    
    if not backend_config:
        raise StorageError(
            f"Backend '{backend_type.value}' not configured. "
            f"Run 'dtm config --backend {backend_type.value}' to configure."
        )
    
    return backend_config


def save_backend_config(backend_type: BackendType, remote_uri: str, 
                       credentials_path: Optional[str] = None) -> None:
    """
    Save backend configuration to global config file.
    
    Args:
        backend_type: Type of backend to configure
        remote_uri: Remote URI for the backend
        credentials_path: Optional path to credentials file
    """
    config_path = get_config_path()
    
    # Load existing config or create new
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
    
    # Ensure backends section exists
    if "backends" not in config:
        config["backends"] = {}
    
    # Update backend config
    config["backends"][backend_type.value] = {
        "remote_uri": remote_uri
    }
    
    if credentials_path:
        config["backends"][backend_type.value]["credentials_path"] = credentials_path
    
    # Save config
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def initialize_default_config() -> None:
    """
    Initialize default config file with local backend.
    
    This should be called on package install or first use.
    """
    config_path = get_config_path()
    
    # Don't overwrite existing config
    if config_path.exists():
        return
    
    # Create default config with local backend
    default_storage = get_datamole_dir() / "storage"
    save_backend_config(BackendType.LOCAL, str(default_storage))


def create_storage_backend(backend_type: BackendType) -> StorageBackend:
    """
    Factory function to create storage backend instances.
    
    Loads backend configuration from global config file.
    
    Args:
        backend_type: Type of backend to create
        
    Returns:
        StorageBackend instance
        
    Raises:
        StorageError: If backend config not found or backend not implemented
    """
    # Load backend config from global config
    backend_config = load_backend_config(backend_type)
    remote_uri = backend_config["remote_uri"]
    credentials_path = backend_config.get("credentials_path")
    
    if backend_type == BackendType.LOCAL:
        return LocalStorageBackend(remote_uri)
    elif backend_type == BackendType.GCS:
        # TODO: Implement GCS backend
        raise NotImplementedError("GCS backend not yet implemented")
    elif backend_type == BackendType.S3:
        # TODO: Implement S3 backend
        raise NotImplementedError("S3 backend not yet implemented")
    elif backend_type == BackendType.AZURE:
        # TODO: Implement Azure backend
        raise NotImplementedError("Azure backend not yet implemented")
    else:
        raise StorageError(f"Unsupported backend type: {backend_type}")
