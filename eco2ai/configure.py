"""Show and set the settings folder and the results folder for this worktree."""

import argparse
import json
import os
import sys

from eco2ai.utils import describe_folders


def main(argv=None):
    """
        Print the active settings folder and results folder.
        --settings-dir and --results-dir store those paths in ./.eco2ai/config.json
        and then print the same two lines.
        This command does not ask questions and does not run on import.
    """
    parser = argparse.ArgumentParser(
        description="Show or set the eco2ai settings folder and results folder."
    )
    parser.add_argument(
        "--settings-dir",
        help="Directory whose config.json holds country, region, cpu_sockets, and set_params defaults.",
    )
    parser.add_argument(
        "--results-dir",
        help="Directory joined to a relative file_name. An absolute file_name ignores it.",
    )
    args = parser.parse_args(argv)
    if args.settings_dir is not None or args.results_dir is not None:
        _write_worktree_config(args.settings_dir, args.results_dir)
    print(describe_folders(), end="")
    return 0


def _write_worktree_config(settings_dir, results_dir):
    directory = os.path.join(os.getcwd(), ".eco2ai")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "config.json")
    current = _read_object(path)
    if not current:
        current = _read_object(os.path.join(directory, "config.txt"))
    if settings_dir is not None:
        current["settings_dir"] = os.path.abspath(os.path.expanduser(settings_dir))
    if results_dir is not None:
        current["results_dir"] = os.path.abspath(os.path.expanduser(results_dir))
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(current, handle)
        handle.write("\n")
    os.replace(temporary, path)
    legacy = os.path.join(directory, "config.txt")
    if os.path.isfile(legacy):
        os.remove(legacy)


def _read_object(path):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


if __name__ == "__main__":
    sys.exit(main())
