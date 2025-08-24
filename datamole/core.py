"""
Main logic for datamole core functions. Provides the DataMole class API.
"""

import os
import getpass

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

    def init(self):
        """Initialize datamole in a repo."""
        if os.path.exists(self.datamole_file):
            print(".datamole already exists. Initialization skipped.")
            return
        meta = {
            "project": self.project_name,
            "versions": []
        }
        import json
        with open(self.datamole_file, 'w') as f:
            json.dump(meta, f, indent=2)
        print(f"Initialized datamole for project '{self.project_name}'.")

    def add_version(self, data_dir):
        """Create and track a new version."""
        # Placeholder: compute hash, copy to remote, update .datamole
        print(f"Adding version for {data_dir} (not implemented)")

    def list_versions(self):
        """Show all known tracked versions."""
        if not os.path.exists(self.datamole_file):
            print("No .datamole file found.")
            return
        import json
        with open(self.datamole_file) as f:
            meta = json.load(f)
        for v in meta.get("versions", []):
            print(v)

    def pull_version(self, version_hash, target_path):
        """Retrieve a specific version from remote."""
        print(f"Pulling version {version_hash} to {target_path} (not implemented)")

    def current_version(self):
        """Show current version checked out."""
        print("Current version: (not implemented)")

    def delete_version(self, version_hash):
        """Delete a version (with permissions check)."""
        print(f"Deleting version {version_hash} (not implemented)")
