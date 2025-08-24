"""
CLI parser for datamole using argparse (or swap to typer if desired).
"""


import argparse
from datamole.core import DataMole


def main():
    parser = argparse.ArgumentParser(prog='dtm', description='datamole CLI')
    subparsers = parser.add_subparsers(dest='command')

    subparsers.add_parser('init')
    add_version_parser = subparsers.add_parser('add-version')
    add_version_parser.add_argument('data_dir')
    subparsers.add_parser('list-versions')
    pull_parser = subparsers.add_parser('pull-version')
    pull_parser.add_argument('version_hash')
    pull_parser.add_argument('--to', dest='target_path', required=True)
    subparsers.add_parser('current-version')
    del_parser = subparsers.add_parser('delete-version')
    del_parser.add_argument('version_hash')

    args = parser.parse_args()

    dtm = DataMole()

    if args.command == 'init':
        dtm.init()
    elif args.command == 'add-version':
        dtm.add_version(args.data_dir)
    elif args.command == 'list-versions':
        dtm.list_versions()
    elif args.command == 'pull-version':
        dtm.pull_version(args.version_hash, args.target_path)
    elif args.command == 'current-version':
        dtm.current_version()
    elif args.command == 'delete-version':
        dtm.delete_version(args.version_hash)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
