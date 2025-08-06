"""
File finder utility for locating the most recent payroll reports.
Handles both new hires and termination reports from OneDrive directories.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

log = logging.getLogger(__name__)


class PayrollFileFinder:
    """Find the most recent payroll report files."""

    # Filename patterns
    NEW_HIRE_PATTERN = re.compile(r"^(\d{14})_New Hires Report_[a-f0-9]+_\.xlsx$")
    TERM_PATTERN = re.compile(r"^(\d{14})_New Terms Report_[a-f0-9]+_\.?xlsx$")

    def __init__(self, hires_dir: Path = None, terms_dir: Path = None):
        """
        Initialize with directory paths.

        Args:
            hires_dir: Directory containing new hire reports
            terms_dir: Directory containing termination reports
        """
        # Use provided paths or defaults from config
        from config import settings

        self.hires_dir = hires_dir or settings.hires_dir
        self.terms_dir = terms_dir or settings.terms_dir

        # Validate directories exist
        if self.hires_dir and not self.hires_dir.exists():
            log.warning(f"Hires directory does not exist: {self.hires_dir}")
        if self.terms_dir and not self.terms_dir.exists():
            log.warning(f"Terms directory does not exist: {self.terms_dir}")

    def find_latest_hire_report(self) -> Optional[Path]:
        """
        Find the most recent new hire report file.

        Returns:
            Path to the most recent file, or None if not found
        """
        return self._find_latest_file(
            self.hires_dir, self.NEW_HIRE_PATTERN, "New Hires"
        )

    def find_latest_term_report(self) -> Optional[Path]:
        """
        Find the most recent termination report file.

        Returns:
            Path to the most recent file, or None if not found
        """
        return self._find_latest_file(self.terms_dir, self.TERM_PATTERN, "New Terms")

    def _find_latest_file(
        self, directory: Path, pattern: re.Pattern, report_type: str
    ) -> Optional[Path]:
        """
        Find the most recent file matching the pattern in the directory.

        Args:
            directory: Directory to search
            pattern: Regex pattern to match filenames
            report_type: Type of report for logging

        Returns:
            Path to the most recent matching file, or None
        """
        if not directory or not directory.exists():
            log.error(f"Directory does not exist: {directory}")
            return None

        matching_files = []

        # Search for matching files
        for file_path in directory.glob("*.xlsx"):
            match = pattern.match(file_path.name)
            if match:
                # Extract timestamp from filename
                timestamp_str = match.group(1)
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                    matching_files.append((timestamp, file_path))
                    log.debug(
                        f"Found {report_type} report: {file_path.name} (timestamp: {timestamp})"
                    )
                except ValueError:
                    log.warning(
                        f"Could not parse timestamp from filename: {file_path.name}"
                    )

        if not matching_files:
            log.warning(f"No {report_type} reports found in {directory}")
            return None

        # Sort by timestamp and get the most recent
        matching_files.sort(key=lambda x: x[0], reverse=True)
        latest_file = matching_files[0][1]

        log.info(f"Found latest {report_type} report: {latest_file.name}")
        log.info(f"  Created: {matching_files[0][0].strftime('%Y-%m-%d %H:%M:%S')}")

        # Log if there are older files
        if len(matching_files) > 1:
            log.debug(f"  ({len(matching_files) - 1} older reports ignored)")

        return latest_file

    def get_file_info(self, file_path: Path) -> dict:
        """
        Get information about a report file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file information
        """
        info = {
            "path": str(file_path),
            "name": file_path.name,
            "size": file_path.stat().st_size if file_path.exists() else 0,
            "exists": file_path.exists(),
        }

        # Try to extract timestamp from filename
        for pattern in [self.NEW_HIRE_PATTERN, self.TERM_PATTERN]:
            match = pattern.match(file_path.name)
            if match:
                timestamp_str = match.group(1)
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                    info["timestamp"] = timestamp.isoformat()
                    info["age_hours"] = (
                        datetime.now() - timestamp
                    ).total_seconds() / 3600
                except ValueError:
                    pass
                break

        return info

    def list_all_reports(self, report_type: str = "both") -> dict:
        """
        List all available reports.

        Args:
            report_type: "hires", "terms", or "both"

        Returns:
            Dictionary with lists of available reports
        """
        result = {}

        if (
            report_type in ["hires", "both"]
            and self.hires_dir
            and self.hires_dir.exists()
        ):
            hire_files = []
            for file_path in self.hires_dir.glob("*.xlsx"):
                if self.NEW_HIRE_PATTERN.match(file_path.name):
                    hire_files.append(self.get_file_info(file_path))
            result["hire_reports"] = sorted(
                hire_files, key=lambda x: x.get("timestamp", ""), reverse=True
            )

        if (
            report_type in ["terms", "both"]
            and self.terms_dir
            and self.terms_dir.exists()
        ):
            term_files = []
            for file_path in self.terms_dir.glob("*.xlsx"):
                if self.TERM_PATTERN.match(file_path.name):
                    term_files.append(self.get_file_info(file_path))
            result["term_reports"] = sorted(
                term_files, key=lambda x: x.get("timestamp", ""), reverse=True
            )

        return result


def get_latest_hire_file() -> Path:
    """
    Convenience function to get the latest hire report.
    Raises exception if not found.
    """
    finder = PayrollFileFinder()
    file_path = finder.find_latest_hire_report()
    if not file_path:
        raise FileNotFoundError(f"No new hire reports found in {finder.hires_dir}")
    return file_path


def get_latest_term_file() -> Path:
    """
    Convenience function to get the latest termination report.
    Raises exception if not found.
    """
    finder = PayrollFileFinder()
    file_path = finder.find_latest_term_report()
    if not file_path:
        raise FileNotFoundError(f"No termination reports found in {finder.terms_dir}")
    return file_path
