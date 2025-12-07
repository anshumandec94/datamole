"""
Configuration and environment utilities for datamole.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict
import yaml


@dataclass
class DataMoleFileConfig:
    """ This dataclass will define the properties that are stored in the .datamole file.
    The datamole_file contains the metadata about the projects and its tracked versions.
    It will also include information such as the data_directory that was/is tracked by the file.
    This would also include a handler for the yaml file that the .datamole file is (the .datamole filetype is for name only and is actually a yaml file).
    
    Version structure: List of dicts with keys:
        - hash: version hash string
        - timestamp: ISO 8601 timestamp
        - message: optional description
    
    Backend: Stores only the backend type (e.g., "local", "gcs", "s3", "azure").
             Full backend config (remote_uri, credentials) is loaded from ~/.datamole/config.yaml
    """

    project: str
    data_directory: Optional[str] = None
    current_version: Optional[str] = None
    backend_type: Optional[str] = None
    versions: List[Dict[str, str]] = field(default_factory=list)
    _file_path: Optional[str] = field(default=None, init=False, repr=False)

    @classmethod
    def load(cls, file_path: str) -> 'DataMoleFileConfig':
        """Load configuration from existing .datamole file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No .datamole file found at {file_path}")
        
        with open(file_path) as f:
            data = yaml.safe_load(f)
        
        config = cls(
            project=data.get("project", ""),
            data_directory=data.get("data_directory", None),
            current_version=data.get("current_version", None),
            backend_type=data.get("backend_type", None),
            versions=data.get("versions", []),
        )
        config._file_path = file_path
        return config
    
    @classmethod
    def create(cls, file_path: str, project: str, data_directory: Optional[str] = None, 
               backend_type: str = "local") -> 'DataMoleFileConfig':
        """Create a new .datamole file with initial configuration.
        
        Note: Backend configuration (remote_uri, credentials) is not stored in .datamole.
        It is managed globally in ~/.datamole/config.yaml
        """
        # Validate the directory exists and is writable
        directory = os.path.dirname(file_path) or '.'
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory does not exist: {directory}")
        if not os.access(directory, os.W_OK):
            raise PermissionError(f"Directory is not writable: {directory}")
        if os.path.exists(file_path):
            raise FileExistsError(f"File already exists: {file_path}")
        
        # Validate data_directory is relative path
        if data_directory and os.path.isabs(data_directory):
            raise ValueError(f"data_directory must be a relative path, got: {data_directory}")

        config = cls(project=project, data_directory=data_directory, backend_type=backend_type)
        config._file_path = file_path
        config.save()
        return config
    
    def save(self):
        """Save the current config to the .datamole file."""
        if not self._file_path:
            raise ValueError("File path for .datamole file is not set.")
        
        # Validate the directory exists and is writable
        directory = os.path.dirname(self._file_path) or '.'
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory does not exist: {directory}")
        if not os.access(directory, os.W_OK):
            raise PermissionError(f"Directory is not writable: {directory}")
        
        data = {
            "project": self.project,
            "data_directory": self.data_directory,
            "current_version": self.current_version,
            "backend_type": self.backend_type,
            "versions": self.versions,
        }
        with open(self._file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def get_absolute_data_path(self) -> str:
        """Resolve data_directory to absolute path based on .datamole file location."""
        if not self._file_path:
            raise ValueError("File path not set, cannot resolve data directory")
        if not self.data_directory:
            raise ValueError("data_directory not configured")
        
        # Get directory containing .datamole file
        config_dir = os.path.dirname(self._file_path) or '.'
        # Resolve relative data_directory to absolute path
        return os.path.abspath(os.path.join(config_dir, self.data_directory))
    
    @staticmethod
    def validate_tag(tag: str) -> str:
        """Validate and normalize a tag.
        
        Args:
            tag: Tag string to validate
            
        Returns:
            Normalized tag (stripped, validated)
            
        Raises:
            ValueError: If tag is invalid
        """
        # Strip whitespace
        tag = tag.strip()
        
        if not tag:
            raise ValueError("Tag cannot be empty")
        
        # Allow alphanumeric, hyphen, underscore, dot
        if not re.match(r'^[a-zA-Z0-9._-]+$', tag):
            raise ValueError(
                f"Tag '{tag}' contains invalid characters. "
                f"Only alphanumeric characters, hyphens, underscores, and dots are allowed."
            )
        
        return tag
    
    def add_version_entry(self, version_hash: str, timestamp: str, 
                         message: Optional[str] = None, tag: Optional[str] = None):
        """Add a new version entry to the versions list.
        
        Args:
            version_hash: 8-character hex hash
            timestamp: ISO 8601 timestamp
            message: Optional description
            tag: Optional tag for easy lookup (must be unique)
            
        Raises:
            ValueError: If tag is invalid or already exists
        """
        # Validate and check tag uniqueness
        if tag:
            tag = self.validate_tag(tag)
            if self.has_tag(tag):
                raise ValueError(f"Tag '{tag}' already exists. Tags must be unique.")
        
        version_entry = {
            "hash": version_hash,
            "timestamp": timestamp,
        }
        if message:
            version_entry["message"] = message
        if tag:
            version_entry["tag"] = tag
        
        self.versions.append(version_entry)
        self.save()
    
    def get_latest_version(self) -> Optional[str]:
        """Get the hash of the most recent version (last in list)."""
        if not self.versions:
            return None
        return self.versions[-1]["hash"]
    
    def has_version(self, version_hash: str) -> bool:
        """Check if a version hash exists in the versions list."""
        return any(v["hash"] == version_hash for v in self.versions)
    
    def get_version_info(self, version_hash: str) -> Optional[Dict[str, str]]:
        """Get version metadata for a specific hash."""
        for version in self.versions:
            if version["hash"] == version_hash:
                return version
        return None
    
    def get_version_by_tag(self, tag: str) -> Optional[Dict[str, str]]:
        """Get version metadata for a specific tag.
        
        Args:
            tag: Tag to search for (case-sensitive)
            
        Returns:
            Version dict if found, None otherwise
        """
        for version in self.versions:
            if version.get("tag") == tag:
                return version
        return None
    
    def has_tag(self, tag: str) -> bool:
        """Check if a tag already exists.
        
        Args:
            tag: Tag to check
            
        Returns:
            True if tag exists, False otherwise
        """
        return any(v.get("tag") == tag for v in self.versions)
    
    def get_versions_by_hash_prefix(self, prefix: str) -> List[Dict[str, str]]:
        """Get versions matching a hash prefix.
        
        Args:
            prefix: Hash prefix to match (minimum 4 characters)
            
        Returns:
            List of matching version dicts
            
        Raises:
            ValueError: If prefix is too short
        """
        if len(prefix) < 4:
            raise ValueError(f"Hash prefix must be at least 4 characters, got: {prefix}")
        
        matches = []
        for version in self.versions:
            if version["hash"].startswith(prefix):
                matches.append(version)
        
        return matches
