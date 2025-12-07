"""
Global datamole configuration management (~/.datamole/config.yaml).

This module handles the global configuration that stores backend credentials
and settings shared across all datamole projects.
"""

import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

from datamole.storage import BackendType


class GlobalConfig:
    """Manages global datamole configuration at ~/.datamole/config.yaml.
    
    This is a singleton class that handles backend authentication and global settings.
    The configuration is loaded once and cached in memory.
    
    Config structure:
        backends:
            local:
                storage_path: /path/to/storage
            gcs:
                service_account_json: /path/to/credentials.json
                default_bucket: my-bucket
            s3:
                aws_profile: default
                default_bucket: my-bucket
    """
    
    _instance: Optional['GlobalConfig'] = None
    _lock = threading.Lock()
    
    def __init__(self, config_data: Dict[str, Any]):
        """Initialize GlobalConfig with loaded data.
        
        Use GlobalConfig.load() to create instances, not this constructor directly.
        """
        self._config = config_data
    
    @staticmethod
    def get_config_dir() -> Path:
        """Get the global datamole configuration directory (~/.datamole)."""
        home = Path(os.environ.get('HOME', str(Path.home())))
        return home / ".datamole"
    
    @staticmethod
    def get_config_path() -> Path:
        """Get the path to global config file (~/.datamole/config.yaml)."""
        return GlobalConfig.get_config_dir() / "config.yaml"
    
    @classmethod
    def _load_from_disk(cls) -> 'GlobalConfig':
        """Load configuration from disk (internal method)."""
        config_path = cls.get_config_path()
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Global datamole configuration not found at: {config_path}\n\n"
                f"Please run the setup wizard first:\n"
                f"  dtm config\n\n"
                f"Or configure manually:\n"
                f"  dtm config --backend local --storage-path ~/.datamole/storage"
            )
        
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
        
        return cls(config_data)
    
    @classmethod
    def load(cls) -> 'GlobalConfig':
        """Load global config from ~/.datamole/config.yaml (singleton).
        
        Returns the cached instance if already loaded, otherwise loads from disk.
        
        Returns:
            GlobalConfig instance
            
        Raises:
            FileNotFoundError: If config file doesn't exist with instructions
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls._load_from_disk()
            return cls._instance
    
    @classmethod
    def reload(cls) -> 'GlobalConfig':
        """Force reload configuration from disk.
        
        Useful after running 'dtm config' to pick up changes.
        
        Returns:
            GlobalConfig instance with fresh data
        """
        with cls._lock:
            cls._instance = cls._load_from_disk()
            return cls._instance
    
    def get_backend_config(self, backend_type: BackendType) -> Dict[str, Any]:
        """Get configuration for a specific backend.
        
        Args:
            backend_type: The backend to get config for
            
        Returns:
            Backend configuration dict
            
        Raises:
            RuntimeError: If backend is not configured with clear instructions
        """
        backends = self._config.get('backends', {})
        backend_key = backend_type.value
        
        if backend_key not in backends:
            raise RuntimeError(
                f"Backend '{backend_key}' is not configured!\n\n"
                f"Please run: dtm config --backend {backend_key}\n"
                f"Or manually edit: {self.get_config_path()}"
            )
        
        return backends[backend_key]
    
    def set_backend_config(self, backend_type: BackendType, **config: Any):
        """Set or update configuration for a backend.
        
        Args:
            backend_type: The backend to configure
            **config: Configuration key-value pairs
        """
        if 'backends' not in self._config:
            self._config['backends'] = {}
        
        self._config['backends'][backend_type.value] = config
    
    def save(self):
        """Save current configuration to disk."""
        config_path = self.get_config_path()
        config_dir = self.get_config_dir()
        
        # Ensure directory exists
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Write config
        with open(config_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def initialize_defaults(cls) -> 'GlobalConfig':
        """Create a new global config with sensible defaults.
        
        Creates ~/.datamole/config.yaml with local backend configured
        to use ~/.datamole/storage as the default storage location.
        
        Returns:
            GlobalConfig instance
        """
        config_dir = cls.get_config_dir()
        config_path = cls.get_config_path()
        
        # Create directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create default config
        default_config = {
            'backends': {
                'local': {
                    'storage_path': str(config_dir / 'storage')
                }
            }
        }
        
        # Write config
        with open(config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
        
        # Return loaded instance
        with cls._lock:
            cls._instance = cls(default_config)
            return cls._instance
