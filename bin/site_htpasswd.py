#!/usr/bin/env python
"""Apache-compatible .htpasswd generation for optional site-wide HTTP Basic auth."""

import os
import subprocess

CONFIG_SITE_USERNAME_KEY = "site_username"
CONFIG_SITE_PASSWORD_KEY = "site_password"
SITE_HTPASSWD_FILENAME = ".htpasswd"
SITE_HTPASSWD_PUBLIC_SUBDIR = "public_html"
SITE_HTPASSWD_BCRYPT_COST = 10
HTPASSWD_BINARY = "htpasswd"
OPENSSL_BINARY = "openssl"


class SiteHtpasswdError(Exception):
    """Raised when site auth credentials are invalid or hashing tools are unavailable."""


def _normalize_optional_username(value):
    """Return stripped username or None if missing or blank."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise SiteHtpasswdError(f"{CONFIG_SITE_USERNAME_KEY} must be a string when set")
    stripped = value.strip()
    return stripped if stripped else None


def _require_password_str(value):
    """Validate site_password type; return the string unchanged (no strip)."""
    if not isinstance(value, str):
        raise SiteHtpasswdError(f"{CONFIG_SITE_PASSWORD_KEY} must be a string when set")
    return value


def _htpasswd_line_bcrypt(username, password):
    """Return one htpasswd line using bcrypt via apache htpasswd, or None on failure."""
    cost = str(SITE_HTPASSWD_BCRYPT_COST)
    try:
        proc = subprocess.run(
            [HTPASSWD_BINARY, "-nBiC", cost, username],
            input=password.encode("utf-8"),
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    line = proc.stdout.decode("utf-8").strip()
    if not line or not line.startswith(f"{username}:"):
        return None
    return line + ("\n" if not line.endswith("\n") else "")


def _htpasswd_line_apr1(username, password):
    """Return one htpasswd line using APR1 via openssl passwd, or None on failure."""
    try:
        proc = subprocess.run(
            [OPENSSL_BINARY, "passwd", "-apr1", "-stdin"],
            input=password.encode("utf-8"),
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    digest = proc.stdout.decode("utf-8").strip()
    if not digest or digest.startswith("password:"):
        return None
    return f"{username}:{digest}\n"


def build_htpasswd_line(username, password):
    """Build a single htpasswd line for username and password.

    Tries bcrypt (htpasswd) first, then APR1 (openssl). Password is passed on stdin only.

    Raises:
        SiteHtpasswdError: If no hashing tool succeeds.
    """
    line = _htpasswd_line_bcrypt(username, password)
    if line:
        return line
    line = _htpasswd_line_apr1(username, password)
    if line:
        return line
    raise SiteHtpasswdError(
        f"Could not generate {SITE_HTPASSWD_FILENAME}: need `{HTPASSWD_BINARY}` (bcrypt) "
        f"or `{OPENSSL_BINARY} passwd -apr1` on PATH."
    )


def write_site_htpasswd_from_config(config, output_path):
    """Write public_html/.htpasswd when both site username and password are set.

    Args:
        config (dict): Top-level YAML config.
        output_path (str): Config output_path (directory containing public_html).

    Returns:
        str: "written" if the file was created or updated, "skipped" if auth keys absent.

    Raises:
        SiteHtpasswdError: If only one of the two keys is set, types are wrong, or hashing fails.
    """
    user = _normalize_optional_username(config.get(CONFIG_SITE_USERNAME_KEY))
    password_present = CONFIG_SITE_PASSWORD_KEY in config
    password_raw = config.get(CONFIG_SITE_PASSWORD_KEY)

    if user is None and not password_present:
        return "skipped"
    if user is None or not password_present:
        raise SiteHtpasswdError(
            f"Set both {CONFIG_SITE_USERNAME_KEY} and {CONFIG_SITE_PASSWORD_KEY}, or omit both."
        )

    password = _require_password_str(password_raw)
    if not password:
        raise SiteHtpasswdError(f"{CONFIG_SITE_PASSWORD_KEY} must be non-empty when {CONFIG_SITE_USERNAME_KEY} is set")

    line = build_htpasswd_line(user, password)
    dest_dir = os.path.join(output_path, SITE_HTPASSWD_PUBLIC_SUBDIR)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, SITE_HTPASSWD_FILENAME)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(line)
    os.chmod(dest_path, 0o600)
    return "written"
