"""Path resolution for Perplexity CLI configuration files."""

import os
from pathlib import Path

_DEFAULT_HOME = Path.home() / ".perplexity"


def get_home_dir() -> Path:
    """Return the Perplexity config home directory.

    Respects PERPLEXITY_HOME environment variable, defaults to ~/.perplexity/.
    Creates the directory if it doesn't exist.
    """
    home = Path(os.environ.get("PERPLEXITY_HOME", str(_DEFAULT_HOME)))
    home.mkdir(parents=True, exist_ok=True)
    return home


def get_storage_path() -> Path:
    """Return the path to the Playwright storage state file."""
    return get_home_dir() / "storage_state.json"


def get_browser_profile_dir() -> Path:
    """Return the path to the persistent browser profile directory."""
    profile_dir = get_home_dir() / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def get_threads_dir() -> Path:
    """Return the path to the directory storing named thread contexts."""
    threads_dir = get_home_dir() / "threads"
    threads_dir.mkdir(parents=True, exist_ok=True)
    return threads_dir
