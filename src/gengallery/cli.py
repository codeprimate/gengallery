"""gengallery CLI: argparse construction, parse, dispatch only."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from gengallery import __version__
from gengallery.commands import init as cmd_init
from gengallery.commands import push as cmd_push
from gengallery.commands import serve as cmd_serve
from gengallery.commands import update as cmd_update
from gengallery.constants import (
    CLI_APP_NAME,
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

    return parser


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
