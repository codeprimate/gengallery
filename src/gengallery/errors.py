"""User-facing CLI errors (distinct from programming bugs)."""


class CliUserError(Exception):
    """Raised for invalid input, missing files, or invalid config; mapped to stderr + exit code."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
