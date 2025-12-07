"""
Configuration management for datamole.

This module provides configuration classes for both project-level
and global datamole settings.
"""

from datamole.config.project import ProjectConfig
from datamole.config.global_config import GlobalConfig

# For backwards compatibility - can be removed in future versions
DataMoleFileConfig = ProjectConfig

__all__ = ['ProjectConfig', 'GlobalConfig', 'DataMoleFileConfig']
