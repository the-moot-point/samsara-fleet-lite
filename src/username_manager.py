"""
Username manager for handling duplicate checking and persistence.
Ensures all usernames are unique across Samsara platform.
"""
import pandas as pd
from pathlib import Path
from typing import Set
import logging
import threading

log = logging.getLogger(__name__)


class UsernameManager:
    """Thread-safe manager for username uniqueness and persistence."""

    def __init__(self, csv_path: Path = None):
        """
        Initialize username manager.

        Args:
            csv_path: Path to usernames.csv file. Defaults to data/usernames.csv
        """
        self.csv_path = csv_path or (Path(__file__).parent.parent / "data" / "usernames.csv")
        self._lock = threading.Lock()
        self._usernames: Set[str] = set()
        self._load_usernames()

    def _load_usernames(self) -> None:
        """Load existing usernames from CSV file."""
        if self.csv_path.exists():
            try:
                df = pd.read_csv(self.csv_path, dtype=str)
                # Handle different possible column names
                if 'username' in df.columns:
                    self._usernames = set(df['username'].dropna().str.lower())
                elif 'Username' in df.columns:
                    self._usernames = set(df['Username'].dropna().str.lower())
                else:
                    # If no header or different header, assume first column
                    self._usernames = set(df.iloc[:, 0].dropna().str.lower())
                log.info(f"Loaded {len(self._usernames)} existing usernames from {self.csv_path}")
            except Exception as e:
                log.error(f"Error loading usernames from {self.csv_path}: {e}")
                self._usernames = set()
        else:
            log.info(f"No existing username file found at {self.csv_path}, starting fresh")
            self._usernames = set()
            # Create the file with header
            self._save_usernames()

    def _save_usernames(self) -> None:
        """Save current username set to CSV file."""
        try:
            # Ensure directory exists
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)

            # Save as DataFrame with single column
            df = pd.DataFrame({'username': sorted(self._usernames)})
            df.to_csv(self.csv_path, index=False)
            log.debug(f"Saved {len(self._usernames)} usernames to {self.csv_path}")
        except Exception as e:
            log.error(f"Error saving usernames to {self.csv_path}: {e}")
            raise

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
                self._save_usernames()
                return username

            # Try appending numbers until we find a unique one
            counter = 2
            while True:
                candidate = f"{username}{counter}"
                if candidate not in self._usernames:
                    self._usernames.add(candidate)
                    self._save_usernames()
                    log.info(f"Username '{username}' was taken, using '{candidate}' instead")
                    return candidate
                counter += 1

                # Safety check to prevent infinite loop
                if counter > 9999:
                    raise ValueError(f"Unable to generate unique username for base: {username}")

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
                self._save_usernames()
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
                self._save_usernames()
                log.info(f"Synced with Samsara: added {after_count - before_count} new usernames")


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