
import os
import shutil
import tempfile
import yaml
import pytest
from datamole.core import DataMole

# --- Fixtures and helpers ---

@pytest.fixture
def temp_repo(monkeypatch):
    temp_dir = tempfile.mkdtemp()
    cwd = os.getcwd()
    monkeypatch.chdir(temp_dir)
    try:
        yield temp_dir
    finally:
        monkeypatch.chdir(cwd)
        shutil.rmtree(temp_dir)

def create_data_dir(base, name="data", files=None):
    data_dir = os.path.join(base, name)
    os.makedirs(data_dir, exist_ok=True)
    files = files or ["a.txt", "b.txt"]
    for fname in files:
        with open(os.path.join(data_dir, fname), "w") as f:
            f.write(f"content for {fname}")
    return data_dir

def create_dtmignore(base, patterns=None):
    patterns = patterns or ["*.tmp", "ignoreme.txt"]
    with open(os.path.join(base, ".dtmignore"), "w") as f:
        for pat in patterns:
            f.write(pat + "\n")

@pytest.fixture
def repo_with_versions(temp_repo):
    dtm = DataMole()
    dtm.init()
    # Create and add two versions
    d1 = create_data_dir(temp_repo, "data1", ["a.txt", "b.txt"])
    dtm.add_version(d1)
    d2 = create_data_dir(temp_repo, "data2", ["c.txt", "d.txt"])
    dtm.add_version(d2)
    return dtm, temp_repo

def test_init_creates_datamole_file(temp_repo):
    dtm = DataMole()
    dtm.init()
    assert os.path.exists(".datamole")
    with open(".datamole") as f:
        meta = yaml.safe_load(f)
    assert meta["project"] == os.path.basename(temp_repo)
    assert meta["versions"] == []

def test_init_skips_if_exists(temp_repo):
    # Create a valid .datamole file
    import yaml
    config_data = {
        "project": "test_repo",
        "data_directory": "data",
        "backend_type": "local",
        "current_version": None,
        "versions": []
    }
    with open(".datamole", "w") as f:
        yaml.dump(config_data, f)
    
    dtm = DataMole()
    dtm.init()  # Should not overwrite, just load existing
    
    # Verify original content preserved
    with open(".datamole") as f:
        reloaded = yaml.safe_load(f)
    assert reloaded["project"] == "test_repo"
    assert reloaded["data_directory"] == "data"

def test_list_versions_empty(temp_repo):
    dtm = DataMole()
    dtm.init()
    # Should print nothing for versions
    dtm.list_versions() #TODO: add the assertion once the yaml access is figured out.

    

def test_add_version_placeholder(temp_repo):
    dtm = DataMole()
    dtm.init()
    data_dir = create_data_dir(temp_repo)
    dtm.add_version(data_dir)  # Just checks no error for now

def test_pull_version_placeholder(temp_repo):
    dtm = DataMole()
    dtm.init()
    # pull() without version would try to pull current_version which is None
    # This test is just checking the method exists, skip actual pull
    assert hasattr(dtm, 'pull')

def test_current_version_placeholder(temp_repo):
    dtm = DataMole()
    dtm.init()
    dtm.show_current_version()  # Just checks no error for now

def test_delete_version_placeholder(temp_repo):
    dtm = DataMole()
    dtm.init()
    dtm.delete_version("hash")  # Just checks no error for now

# --- Test for .dtmignore functionality ---
def test_dtmignore_excludes_files(temp_repo):
    dtm = DataMole()
    dtm.init()
    # Create data dir with files, some to ignore
    data_dir = create_data_dir(temp_repo, files=["a.txt", "b.tmp", "ignoreme.txt"])
    create_dtmignore(temp_repo, patterns=["*.tmp", "ignoreme.txt"])
    # This test will need dtm.add_version to respect .dtmignore in the future
    # For now, just check that .dtmignore exists and is readable
    assert os.path.exists(os.path.join(temp_repo, ".dtmignore"))
    with open(os.path.join(temp_repo, ".dtmignore")) as f:
        lines = [l.strip() for l in f if l.strip()]
    assert "*.tmp" in lines and "ignoreme.txt" in lines
