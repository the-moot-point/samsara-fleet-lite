from src.models import DriverAddPayload
from config import settings
from username_manager import get_username_manager
import re
import logging
import pandas as pd
from mapping_loader import (
    load_position_tags,
    load_location_tags_and_timezones,
    load_never_positions,
)

# cache mappings
_POS_TAGS = load_position_tags()
_LOC_MAP = load_location_tags_and_timezones()
_EXCLUDE_POS = load_never_positions()
_USERNAME_MGR = get_username_manager()
_log = logging.getLogger(__name__)


def _generate_base_username(first: str, last: str) -> str:
    """Generate the base username (first initial + last name)."""
    return re.sub(r"[^a-z0-9]", "", f"{first[0]}{last}".lower())


def _username(first: str, last: str) -> str:
    """
    Generate a unique username for the driver.
    If base username exists, appends numbers until unique.
    """
    base = _generate_base_username(first, last)
    unique = _USERNAME_MGR.make_unique(base)
    return unique


def _generate_paycom_key(first: str, last: str, hire_date) -> str:
    """
    Generate a unique paycom key for external ID.
    Format: firstname-lastname_MM-DD-YYYY
    Example: John-Smith_01-15-2024

    Args:
        first: First name
        last: Last name
        hire_date: Hire date (pandas datetime)

    Returns:
        URL-safe paycom key
    """
    # Remove special characters and spaces, keep only alphanumeric
    first_clean = re.sub(r"[^a-zA-Z0-9]", "", first)
    last_clean = re.sub(r"[^a-zA-Z0-9]", "", last)

    # Format date as MM-DD-YYYY (matching Paycom format)
    date_str = hire_date.strftime("%m-%d-%Y")

    # Combine into key with hyphen between names, underscore before date
    paycom_key = f"{first_clean}-{last_clean}_{date_str}"

    return paycom_key


def row_to_payload(row) -> DriverAddPayload | None:
    # Skip positions in the exclude list
    if row.Position in _EXCLUDE_POS:
        _log.info(
            f"Skipping {row.Legal_Firstname} {row.Legal_Lastname} - position '{row.Position}' is excluded"
        )
        return None

    loc_info = _LOC_MAP.get(row.Work_Location)
    if not loc_info:
        raise ValueError(f"Unknown Work_Location: {row.Work_Location}")

    loc_tag = loc_info["tag_id"]
    tz = loc_info["timezone"] or "America/Chicago"

    pos_tag = None
    if row.Position and not pd.isna(row.Position) and row.Position.strip():
        pos_tag = _POS_TAGS.get(row.Position.strip())
        if not pos_tag:
            _log.warning(
                "Position tag missing: '%s' (row %s %s)",
                row.Position,
                row.Legal_Firstname,
                row.Legal_Lastname,
            )

    tag_ids = [loc_tag]
    if pos_tag:
        tag_ids.append(pos_tag)

    # Generate unique username
    username = _username(row.Legal_Firstname, row.Legal_Lastname)

    # Log if username was modified
    base_username = _generate_base_username(row.Legal_Firstname, row.Legal_Lastname)
    if username != base_username:
        _log.info(
            f"Username modified for uniqueness: {row.Legal_Firstname} {row.Legal_Lastname} -> {username}"
        )

    # Generate paycom key for external ID
    paycom_key = _generate_paycom_key(
        row.Legal_Firstname, row.Legal_Lastname, row.Hire_Date
    )
    _log.debug(
        f"Generated paycom key: {paycom_key} for {row.Legal_Firstname} {row.Legal_Lastname}"
    )

    return DriverAddPayload(
        externalIds={
            "paycomname": paycom_key,  # Add the composite key
            "email": f"{username}@example.com",
        },
        name=f"{row.Legal_Firstname} {row.Legal_Lastname}",
        username=username,
        password=settings.default_password,
        notes=f"Hire Date: {row.Hire_Date:%m-%d-%Y}",
        phone=getattr(row, "Phone", None),
        licenseState=row.State,
        peerGroupTagId=pos_tag,
        tagIds=tag_ids,
        locale="us",
        timezone=tz,
        eldExempt=True,
        eldExemptReason="Short Haul",
    )
