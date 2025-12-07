"""Shared pytest fixtures for datamole tests."""

import pytest
import os
from pathlib import Path

from datamole.storage import BackendType, save_backend_config


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Create a temporary home directory for testing."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    yield fake_home


@pytest.fixture
def temp_project(tmp_path, temp_home):
    """Create a temporary project directory."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    original_dir = os.getcwd()
    os.chdir(project_dir)
    
    yield project_dir
    
    os.chdir(original_dir)


@pytest.fixture
def configured_storage(temp_home):
    """Set up global backend configuration."""
    storage_path = temp_home / "datamole_storage"
    save_backend_config(BackendType.LOCAL, str(storage_path))
    yield storage_path
