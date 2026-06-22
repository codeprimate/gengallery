"""gengallery CLI: argparse construction, parse, dispatch only."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from gengallery import __version__
from gengallery.commands import faces as cmd_faces
from gengallery.commands import init as cmd_init
from gengallery.commands import push as cmd_push
from gengallery.commands import serve as cmd_serve
from gengallery.commands import update as cmd_update
from gengallery.constants import (
    CLI_APP_NAME,
    CMD_FACES,
    CMD_FACES_ASSIGN,
    CMD_FACES_LIST_UNNAMED,
    CMD_FACES_MERGE,
    CMD_FACES_PROPAGATE,
    CMD_FACES_RECLUSTER,
    CMD_FACES_REJECT,
    CMD_FACES_SHOW,
    CMD_FACES_UNASSIGN,
    CMD_INIT,
    CMD_PUSH,
    CMD_PUSH_SSH,
    CMD_SERVE,
    CMD_UPDATE,
    DEFAULT_SERVE_PORT,
)
from gengallery.errors import CliUserError
from gengallery.pathing import load_project_config, normalize_cli_project_path
from gengallery.validation import (
    validate_existing_project_for_update,
    validate_project_root_is_usable_directory,
    validate_serve_artifacts,
    validate_ssh_config,
)

CommandHandler = Callable[[Path, argparse.Namespace], int]

_CLI_CONSOLE = Console()


def print_cli_banner() -> None:
    """Print the version banner as the first stdout line of every CLI invocation."""
    _CLI_CONSOLE.print(
        f"[bold cyan]{CLI_APP_NAME}[/] [dim](v{__version__})[/]"
    )


def _cli_description() -> str:
    tagline = "Static photo gallery build, serve, and deploy."
    return f"{CLI_APP_NAME} {__version__}\n\n{tagline}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=CLI_APP_NAME,
        description=_cli_description(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="COMMAND",
    )

    init_parser = subparsers.add_parser(
        CMD_INIT,
        help="Create project scaffolding and run npm install (Tailwind).",
        description=(
            "Create config.yaml, package.json, a galleries directory with an example gallery, "
            "and Jinja templates under templates/. Then run npm install in the project directory "
            "(requires Node.js and npm on PATH). Missing parent directories are created. "
            "If config.yaml, package.json, galleries, or templates already exist in the target "
            "directory, the command fails (there is no --force or overwrite mode)."
        ),
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PROJECT",
        help="Project directory (default: current working directory).",
    )
    init_parser.set_defaults(handler=cmd_init.run)

    update_parser = subparsers.add_parser(CMD_UPDATE, help="Run the build pipeline.")
    update_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PROJECT",
        help="Project directory (default: current working directory).",
    )
    update_parser.set_defaults(handler=cmd_update.run)

    serve_parser = subparsers.add_parser(CMD_SERVE, help="Serve generated site locally.")
    serve_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PROJECT",
        help="Project directory (default: current working directory).",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SERVE_PORT,
        metavar="PORT",
        help=f"TCP port (default: {DEFAULT_SERVE_PORT}).",
    )
    serve_parser.set_defaults(handler=cmd_serve.run)

    push_parser = subparsers.add_parser(CMD_PUSH, help="Deploy to a remote target.")
    push_subparsers = push_parser.add_subparsers(
        dest="push_provider",
        required=True,
        metavar="PROVIDER",
    )
    ssh_parser = push_subparsers.add_parser(
        CMD_PUSH_SSH,
        help="Deploy via SSH/rsync.",
    )
    ssh_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PROJECT",
        help="Project directory (default: current working directory).",
    )
    ssh_parser.set_defaults(handler=cmd_push.run)

    _add_faces_parser(subparsers)

    return parser


def _add_faces_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register the 'faces' command and all its subcommands."""
    _path_arg = dict(
        dest="path",
        nargs="?",
        default=None,
        metavar="PROJECT",
        help="Project directory (default: current working directory).",
    )

    faces_parser = subparsers.add_parser(
        CMD_FACES,
        help="Face detection, identity labeling, and propagation.",
    )
    faces_subparsers = faces_parser.add_subparsers(
        dest="faces_subcommand",
        required=True,
        metavar="SUBCOMMAND",
    )

    # assign
    assign_p = faces_subparsers.add_parser(
        CMD_FACES_ASSIGN,
        help="Add positive label(s) for an identity.",
    )
    assign_p.add_argument("slug", help="Identity slug (e.g. 'alice').")
    assign_p.add_argument(
        "paths", nargs="+", metavar="PATH", help="Image path(s) (gallery/file.jpg)."
    )
    assign_p.add_argument(
        "--face", type=int, default=None, metavar="N", help="Face index (0-based)."
    )
    assign_p.add_argument(**_path_arg)
    assign_p.set_defaults(handler=cmd_faces.run_assign)

    # unassign
    unassign_p = faces_subparsers.add_parser(
        CMD_FACES_UNASSIGN,
        help="Remove positive label(s).",
    )
    unassign_p.add_argument("paths", nargs="+", metavar="PATH", help="Image path(s).")
    unassign_p.add_argument("--face", type=int, default=None, metavar="N", help="Face index.")
    unassign_p.add_argument(**_path_arg)
    unassign_p.set_defaults(handler=cmd_faces.run_unassign)

    # reject
    reject_p = faces_subparsers.add_parser(
        CMD_FACES_REJECT,
        help="Add negative (reject) label(s) for an identity.",
    )
    reject_p.add_argument("slug", help="Identity slug.")
    reject_p.add_argument("paths", nargs="+", metavar="PATH", help="Image path(s).")
    reject_p.add_argument("--face", type=int, default=None, metavar="N", help="Face index.")
    reject_p.add_argument(**_path_arg)
    reject_p.set_defaults(handler=cmd_faces.run_reject)

    # show
    show_p = faces_subparsers.add_parser(
        CMD_FACES_SHOW,
        help="Print detections and write crop JPEGs.",
    )
    show_p.add_argument("paths", nargs="+", metavar="PATH", help="Image path(s).")
    show_p.add_argument(**_path_arg)
    show_p.set_defaults(handler=cmd_faces.run_show)

    # merge
    merge_p = faces_subparsers.add_parser(
        CMD_FACES_MERGE,
        help="Merge source identity into target identity.",
    )
    merge_p.add_argument("source_slug", help="Identity slug to merge from (will be removed).")
    merge_p.add_argument("target_slug", help="Identity slug to merge into.")
    merge_p.add_argument(**_path_arg)
    merge_p.set_defaults(handler=cmd_faces.run_merge)

    # recluster
    recluster_p = faces_subparsers.add_parser(
        CMD_FACES_RECLUSTER,
        help="Drop anonymous cluster assignments and re-cluster unlabeled faces.",
    )
    recluster_p.add_argument(**_path_arg)
    recluster_p.set_defaults(handler=cmd_faces.run_recluster)

    # propagate
    propagate_p = faces_subparsers.add_parser(
        CMD_FACES_PROPAGATE,
        help="Run identity propagation without a full update.",
    )
    propagate_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would change without writing.",
    )
    propagate_p.add_argument(
        "--identity",
        default=None,
        metavar="SLUG",
        help="Limit propagation to a single identity slug.",
    )
    propagate_p.add_argument(**_path_arg)
    propagate_p.set_defaults(handler=cmd_faces.run_propagate)

    # list-unnamed
    list_unnamed_p = faces_subparsers.add_parser(
        CMD_FACES_LIST_UNNAMED,
        help="List anonymous identity clusters for tagging.",
    )
    list_unnamed_p.add_argument(
        "--min-faces",
        type=int,
        default=1,
        metavar="N",
        help="Minimum faces per group (default: 1).",
    )
    list_unnamed_p.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of groups to show.",
    )
    list_unnamed_p.add_argument(
        "--gallery",
        default=None,
        metavar="GALLERY_ID",
        help="Only include faces from this gallery.",
    )
    list_unnamed_p.add_argument(
        "--include-singletons",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include unassigned singleton faces (default: include).",
    )
    list_unnamed_p.add_argument(**_path_arg)
    list_unnamed_p.set_defaults(handler=cmd_faces.run_list_unnamed)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def dispatch(args: argparse.Namespace, *, cwd: Path | None = None) -> int:
    """Resolve project root, validate for the subcommand, invoke handler."""
    base = Path.cwd() if cwd is None else cwd
    project_root = normalize_cli_project_path(getattr(args, "path", None), base)
    validate_project_root_is_usable_directory(
        project_root,
        for_init=(args.command == CMD_INIT),
    )
    if args.command == CMD_INIT:
        handler: CommandHandler = args.handler
        return handler(project_root, args)
    if args.command == CMD_UPDATE:
        validate_existing_project_for_update(project_root)
        handler = args.handler
        return handler(project_root, args)
    if args.command == CMD_FACES:
        validate_existing_project_for_update(project_root)
        handler = args.handler
        return handler(project_root, args)
    config = load_project_config(project_root)
    if args.command == CMD_SERVE:
        validate_serve_artifacts(project_root, config)
        handler = args.handler
        return handler(project_root, args)
    if args.command == CMD_PUSH:
        validate_ssh_config(config)
        handler = args.handler
        return handler(project_root, args)
    raise AssertionError(f"Unexpected command {args.command!r}")


def main(argv: list[str] | None = None) -> None:
    print_cli_banner()
    try:
        args = parse_args(argv)
        code = dispatch(args)
    except CliUserError as e:
        print(e.message, file=sys.stderr)
        raise SystemExit(e.exit_code) from None
    raise SystemExit(code)


def _run_module() -> None:
    """Entry for ``python -m gengallery`` (delegates to ``main``)."""
    main()


if __name__ == "__main__":
    _run_module()
