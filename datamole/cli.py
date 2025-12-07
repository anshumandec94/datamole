"""
CLI for datamole - simple data versioning tool.
"""

import argparse
import sys
from datamole.core import DataMole
from datamole.storage import BackendType


def main():
    parser = argparse.ArgumentParser(
        prog='dtm',
        description='datamole - Simple data versioning for ML projects'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # dtm init
    init_parser = subparsers.add_parser(
        'init',
        help='Initialize datamole in current directory'
    )
    init_parser.add_argument(
        '--data-dir',
        default='data',
        help='Path to data directory (default: data)'
    )
    init_parser.add_argument(
        '--backend',
        default='local',
        choices=['local', 'gcs', 's3', 'azure'],
        help='Storage backend type (default: local)'
    )
    init_parser.add_argument(
        '--no-pull',
        action='store_true',
        help='Skip auto-downloading when .datamole exists'
    )

    # dtm config
    config_parser = subparsers.add_parser(
        'config',
        help='Configure storage backend'
    )
    config_parser.add_argument(
        '--backend',
        required=True,
        choices=['local', 'gcs', 's3', 'azure'],
        help='Backend type to configure'
    )
    config_parser.add_argument(
        '--remote-uri',
        required=True,
        help='Remote storage URI (e.g., /path/to/storage, gs://bucket, s3://bucket)'
    )
    config_parser.add_argument(
        '--credentials',
        help='Path to credentials file (for cloud backends)'
    )

    # dtm add-version
    add_parser = subparsers.add_parser(
        'add-version',
        help='Create a new version from data directory'
    )
    add_parser.add_argument(
        '-m', '--message',
        help='Version description message'
    )
    add_parser.add_argument(
        '-t', '--tag',
        help='Tag name for this version (alphanumeric, -, _, .)'
    )

    # dtm pull
    pull_parser = subparsers.add_parser(
        'pull',
        help='Download a version to data directory'
    )
    pull_parser.add_argument(
        'version',
        nargs='?',
        help='Version to pull (hash, prefix, tag, or "latest"). Defaults to current version'
    )
    pull_parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Overwrite data directory without confirmation'
    )

    # dtm list-versions
    list_parser = subparsers.add_parser(
        'list-versions',
        help='List all versions'
    )

    # dtm current-version
    current_parser = subparsers.add_parser(
        'current-version',
        help='Show current version'
    )

    # dtm delete-version
    delete_parser = subparsers.add_parser(
        'delete-version',
        help='Delete a version (not yet implemented)'
    )
    delete_parser.add_argument('version_hash', help='Version hash to delete')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dtm = DataMole()

    try:
        if args.command == 'init':
            dtm.init(
                data_dir=args.data_dir,
                no_pull=args.no_pull,
                backend=args.backend
            )
        
        elif args.command == 'config':
            dtm.config_backend(
                backend=args.backend,
                remote_uri=args.remote_uri,
                credentials_path=args.credentials
            )
        
        elif args.command == 'add-version':
            dtm.add_version(
                message=args.message,
                tag=args.tag
            )
        
        elif args.command == 'pull':
            dtm.pull(
                version=args.version,
                force=args.force
            )
        
        elif args.command == 'list-versions':
            dtm.list_versions()
        
        elif args.command == 'current-version':
            dtm.show_current_version()
        
        elif args.command == 'delete-version':
            dtm.delete_version(args.version_hash)
        
        else:
            parser.print_help()
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
