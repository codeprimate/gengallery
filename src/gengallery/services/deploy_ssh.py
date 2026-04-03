"""SSH/rsync deploy using site ``config.yaml`` (no shell interpolation)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gengallery.constants import PUBLIC_HTML_SEGMENT
from gengallery.errors import CliUserError
from gengallery.validation import validate_ssh_config


def build_rsync_argv(
    local_export_dir: Path,
    user: str,
    host: str,
    destination: str,
) -> list[str]:
    """Argv for ``rsync -avz --delete`` mirroring legacy trailing-slash semantics."""
    ssh_host = f"{user}@{host}"
    src = local_export_dir.as_posix().rstrip("/") + "/"
    remote = destination.rstrip("/") + "/" if destination else "/"
    return ["rsync", "-avz", "--delete", src, f"{ssh_host}:{remote}"]


def build_ssh_argv(user: str, host: str, remote_command: str) -> list[str]:
    """Argv for non-interactive ``ssh`` with remote command as a single argument."""
    return ["ssh", f"{user}@{host}", remote_command]


def _local_export_dir(project_root: Path, config: dict) -> Path:
    out = (project_root / Path(config["output_path"]) / PUBLIC_HTML_SEGMENT).resolve()
    if not out.is_dir():
        raise CliUserError(
            f"Deploy source directory not found: {out}. Run gengallery update first.",
        )
    return out


def run_deploy(project_root: Path, config: dict) -> None:
    """
    Rsync ``public_html`` to remote, then run each ``post_sync_commands`` over SSH.

    Raises:
        CliUserError: missing local export tree or invalid ssh config.
        subprocess.CalledProcessError: rsync or ssh non-zero exit (message includes argv).
    """
    ssh = validate_ssh_config(config)
    local_dir = _local_export_dir(project_root, config)
    user = str(ssh["user"])
    host = str(ssh["host"])
    destination = str(ssh["destination"])
    group = str(ssh["group"])

    rsync_argv = build_rsync_argv(local_dir, user, host, destination)
    print(f"Running: {' '.join(rsync_argv)}")
    try:
        subprocess.run(rsync_argv, check=True)
    except subprocess.CalledProcessError as e:
        cmd_s = " ".join(str(x) for x in (e.cmd if isinstance(e.cmd, (list, tuple)) else [e.cmd]))
        raise CliUserError(
            f"rsync failed (exit {e.returncode}): {cmd_s}",
        ) from e

    for cmd_template in ssh["post_sync_commands"]:
        formatted = cmd_template.format(
            user=user,
            group=group,
            destination=destination,
        )
        ssh_argv = build_ssh_argv(user, host, formatted)
        print(f"Running: {' '.join(ssh_argv)}")
        try:
            subprocess.run(ssh_argv, check=True)
        except subprocess.CalledProcessError as e:
            cmd_s = " ".join(
                str(x) for x in (e.cmd if isinstance(e.cmd, (list, tuple)) else [e.cmd])
            )
            raise CliUserError(
                f"ssh failed (exit {e.returncode}): {cmd_s}",
            ) from e
