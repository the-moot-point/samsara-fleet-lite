"""
Username manager for handling duplicate checking and persistence.
Ensures all usernames are unique across Samsara platform.

The manager can both generate and register unique usernames via
``make_unique`` and preview the next available username without
modifying state using ``check_available``.
"""

import atexit
import logging
import threading
from pathlib import Path
from typing import Set

import pandas as pd

log = logging.getLogger(__name__)


class UsernameManager:
    """Thread-safe manager for username uniqueness and persistence.

    Besides registering usernames with :meth:`make_unique`, callers can
    use :meth:`check_available` to preview the next available username
    without altering the underlying CSV or in-memory set.
    """

    def __init__(self, csv_path: Path = None):
        """
        Initialize username manager.

        Args:
            csv_path: Path to usernames.csv file. Defaults to data/usernames.csv
        """
        self.csv_path = csv_path or (
            Path(__file__).parent.parent / "data" / "usernames.csv"
        )
        self._lock = threading.Lock()
        self._usernames: Set[str] = set()
        self._pending_count = 0
        self._dirty = False
        atexit.register(self.flush)
        self._load_usernames()

    def _load_usernames(self) -> None:
        """Load existing usernames from CSV file."""
        if self.csv_path.exists():
            try:
                df = pd.read_csv(self.csv_path, dtype=str)
                # Handle different possible column names
                if "username" in df.columns:
                    self._usernames = set(df["username"].dropna().str.lower())
                elif "Username" in df.columns:
                    self._usernames = set(df["Username"].dropna().str.lower())
                else:
                    # If no header or different header, assume first column
                    self._usernames = set(df.iloc[:, 0].dropna().str.lower())
                log.info(
                    f"Loaded {len(self._usernames)} existing usernames from {self.csv_path}"
                )
            except Exception as e:
                log.error(f"Error loading usernames from {self.csv_path}: {e}")
                self._usernames = set()
        else:
            log.info(
                f"No existing username file found at {self.csv_path}, starting fresh"
            )
            self._usernames = set()
            # Create the file with header
            self._save_usernames()

    def _save_usernames(self) -> None:
        """Save current username set to CSV file."""
        try:
            # Ensure directory exists
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)

            # Save as DataFrame with single column
            df = pd.DataFrame({"username": sorted(self._usernames)})
            df.to_csv(self.csv_path, index=False)
            log.debug(f"Saved {len(self._usernames)} usernames to {self.csv_path}")
        except Exception as e:
            log.error(f"Error saving usernames to {self.csv_path}: {e}")
            raise

    def _flush_locked(self) -> None:
        """Flush pending usernames to disk. Lock must be held."""
        if self._dirty:
            self._save_usernames()
            self._pending_count = 0
            self._dirty = False

    def flush(self) -> None:
        """Flush pending usernames to disk."""
        with self._lock:
            self._flush_locked()

    def __del__(self) -> None:
        """Flush pending usernames when the manager is garbage collected."""
        try:
            self.flush()
        except Exception:  # pragma: no cover - best effort
            pass

    def make_unique(self, base_username: str) -> str:
        """
        Generate a unique username based on the provided base.

        If base_username exists, appends numbers (2, 3, 4...) until unique.

        Args:
            base_username: The desired username

        Returns:
            A unique username (either the original or modified)
        """
        with self._lock:
            username = base_username.lower()

            # If it's already unique, return it
            if username not in self._usernames:
                self._usernames.add(username)
                self._pending_count += 1
                self._dirty = True
                if self._pending_count >= 10:
                    self._flush_locked()
                return username

            # Try appending numbers until we find a unique one
            counter = 2
            while True:
                candidate = f"{username}{counter}"
                if candidate not in self._usernames:
                    self._usernames.add(candidate)
                    self._pending_count += 1
                    self._dirty = True
                    if self._pending_count >= 10:
                        self._flush_locked()
                    log.info(
                        f"Username '{username}' was taken, using '{candidate}' instead"
                    )
                    return candidate
                counter += 1

                # Safety check to prevent infinite loop
                if counter > 9999:
                    raise ValueError(
                        f"Unable to generate unique username for base: {username}"
                    )

    def check_available(self, base_username: str) -> str:
        """Return the next available username without persisting it.

        This mirrors the behaviour of :meth:`make_unique` but performs a
        read‑only check. The internal username set and backing CSV remain
        unchanged.

        Args:
            base_username: Desired username to check.

        Returns:
            The username that would be assigned by :meth:`make_unique`.

        Raises:
            ValueError: If no unique username could be found after 9999
                attempts.
        """
        with self._lock:
            username = base_username.lower()
            if username not in self._usernames:
                return username

            counter = 2
            while counter <= 9999:
                candidate = f"{username}{counter}"
                if candidate not in self._usernames:
                    return candidate
                counter += 1

        raise ValueError(
            f"Unable to generate unique username for base: {base_username.lower()}"
        )

    def add_username(self, username: str) -> None:
        """
        Add a username to the set without modification.
        Used when syncing existing Samsara users.

        Args:
            username: Username to add
        """
        with self._lock:
            username_lower = username.lower()
            if username_lower not in self._usernames:
                self._usernames.add(username_lower)
                self._pending_count += 1
                self._dirty = True
                if self._pending_count >= 10:
                    self._flush_locked()
                log.debug(f"Added existing username: {username}")

    def exists(self, username: str) -> bool:
        """
        Check if a username already exists.

        Args:
            username: Username to check

        Returns:
            True if username exists, False otherwise
        """
        return username.lower() in self._usernames

    def get_all_usernames(self) -> Set[str]:
        """
        Get a copy of all registered usernames.

        Returns:
            Set of all usernames (lowercase)
        """
        with self._lock:
            return self._usernames.copy()

    def sync_with_samsara(self, samsara_usernames: Set[str]) -> None:
        """
        Sync local username cache with usernames from Samsara.
        Useful for initial setup or periodic sync.

        Args:
            samsara_usernames: Set of usernames from Samsara API
        """
        with self._lock:
            before_count = len(self._usernames)
            self._usernames.update(username.lower() for username in samsara_usernames)
            after_count = len(self._usernames)

            if after_count > before_count:
                new_count = after_count - before_count
                self._pending_count += new_count
                self._dirty = True
                if self._pending_count >= 10:
                    self._flush_locked()
                log.info(f"Synced with Samsara: added {new_count} new usernames")


# Global singleton instance
_username_manager = None


def get_username_manager(csv_path: Path = None) -> UsernameManager:
    """
    Get the singleton UsernameManager instance.

    Args:
        csv_path: Optional path to usernames.csv (only used on first call)

    Returns:
        The UsernameManager singleton
    """
    global _username_manager
    if _username_manager is None:
        _username_manager = UsernameManager(csv_path)
    return _username_manager
