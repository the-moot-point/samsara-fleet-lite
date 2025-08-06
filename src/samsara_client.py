"""
Lightweight Samsara REST wrapper shared by add/update/deactivate flows.
Enhanced with external ID support for reliable driver matching.
"""
from __future__ import annotations
import os, logging, backoff, requests
from typing import Iterator, Any, Dict, List, Optional, Literal
from pydantic import BaseModel
from urllib.parse import quote

log = logging.getLogger(__name__)
_API = "https://api.samsara.com/v1"
TOKEN = os.getenv("SAMSARA_BEARER_TOKEN")
SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})

@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=5)
def _req(method: str, url: str, **kw) -> Any:
    resp = SESSION.request(method, _API + url, timeout=10, **kw)
    if resp.status_code >= 400:
        log.error("Samsara %s %s → %s • %s", method, url, resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()

def get_drivers_by_status(status: Literal["active", "deactivated"] = "active") -> List[Dict]:
    """
    Get drivers filtered by activation status.

    Args:
        status: Either "active" or "deactivated"

    Returns:
        List of driver dictionaries
    """
    page_token = None
    out: list[dict] = []

    log.info(f"Fetching {status} drivers from Samsara...")

    while True:
        params = {"driverActivationStatus": status}
        if page_token:
            params["after"] = page_token

        payload = _req("GET", "/fleet/drivers", params=params)
        drivers = payload.get("drivers", [])
        out.extend(drivers)

        page_token = payload.get("pagination", {}).get("after")
        if not page_token:
            break

    log.info(f"Retrieved {len(out)} {status} drivers")
    return out

def get_all_drivers(include_deactivated: bool = True) -> List[Dict]:
    """
    Get all drivers from Samsara.

    Args:
        include_deactivated: If True, fetches both active and deactivated drivers.
                           If False, only fetches active drivers.

    Returns:
        List of all driver dictionaries
    """
    # Always get active drivers
    active_drivers = get_drivers_by_status("active")

    if not include_deactivated:
        return active_drivers

    # Also get deactivated drivers
    deactivated_drivers = get_drivers_by_status("deactivated")

    # Combine both lists
    all_drivers = active_drivers + deactivated_drivers
    log.info(f"Total drivers retrieved: {len(all_drivers)} ({len(active_drivers)} active, {len(deactivated_drivers)} deactivated)")

    return all_drivers

def get_driver_usernames(include_deactivated: bool = True) -> Dict[str, str]:
    """
    Get a mapping of all driver usernames to their activation status.
    Useful for username deduplication checks.

    Args:
        include_deactivated: If True, includes deactivated drivers

    Returns:
        Dict mapping username to status ("active" or "deactivated")
    """
    usernames = {}

    # Get active drivers
    active_drivers = get_drivers_by_status("active")
    for driver in active_drivers:
        if 'username' in driver and driver['username']:
            usernames[driver['username']] = "active"

    if include_deactivated:
        # Get deactivated drivers
        deactivated_drivers = get_drivers_by_status("deactivated")
        for driver in deactivated_drivers:
            if 'username' in driver and driver['username']:
                usernames[driver['username']] = "deactivated"

    log.info(f"Found {len(usernames)} total usernames ({sum(1 for s in usernames.values() if s == 'active')} active, "
             f"{sum(1 for s in usernames.values() if s == 'deactivated')} deactivated)")

    return usernames

def get_driver_by_external_id(external_id_key: str, external_id_value: str) -> Optional[Dict]:
    """
    Get a driver by external ID.

    Args:
        external_id_key: The external ID key (e.g., "paycomname")
        external_id_value: The external ID value (e.g., "John-Smith_01-15-2024")

    Returns:
        Driver dict if found, None if not found or error
    """
    try:
        # URL encode the external ID (key:value format)
        external_id = f"{external_id_key}:{external_id_value}"
        encoded_id = quote(external_id, safe='')

        # Make the API call
        url = f"/fleet/drivers/{encoded_id}"
        driver = _req("GET", url)

        log.info(f"Found driver by external ID: {external_id}")
        return driver

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            log.info(f"Driver not found with external ID: {external_id_key}:{external_id_value}")
            return None
        else:
            log.error(f"Error fetching driver by external ID: {e}")
            raise
    except Exception as e:
        log.error(f"Unexpected error fetching driver by external ID: {e}")
        return None

def update_driver_by_external_id(external_id_key: str, external_id_value: str, patch: dict) -> bool:
    """
    Update a driver using their external ID.

    Args:
        external_id_key: The external ID key (e.g., "paycomname")
        external_id_value: The external ID value (e.g., "John-Smith_01-15-2024")
        patch: Dictionary of fields to update

    Returns:
        True if successful, False otherwise
    """
    try:
        # URL encode the external ID (key:value format)
        external_id = f"{external_id_key}:{external_id_value}"
        encoded_id = quote(external_id, safe='')

        # Make the API call
        url = f"/fleet/drivers/{encoded_id}"
        _req("PATCH", url, json=patch)

        log.info(f"Updated driver by external ID: {external_id}")
        return True

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            log.error(f"Driver not found with external ID: {external_id_key}:{external_id_value}")
            return False
        else:
            log.error(f"Error updating driver by external ID: {e}")
            raise
    except Exception as e:
        log.error(f"Unexpected error updating driver by external ID: {e}")
        return False

def deactivate_driver_by_external_id(external_id_key: str, external_id_value: str, termination_date: str = None) -> bool:
    """
    Deactivate a driver using their external ID.

    Args:
        external_id_key: The external ID key (e.g., "paycomname")
        external_id_value: The external ID value (e.g., "John-Smith_01-15-2024")
        termination_date: Optional termination date string for notes

    Returns:
        True if successful, False otherwise
    """
    patch_data = {"driverActivationStatus": "deactivated"}

    if termination_date:
        patch_data["notes"] = f"Terminated: {termination_date}"

    return update_driver_by_external_id(external_id_key, external_id_value, patch_data)

def add_driver(payload: BaseModel) -> None:
    """Add a new driver to Samsara."""
    _req("POST", "/fleet/drivers", json=payload.dict(exclude_none=True))

def patch_driver(_id: str, patch: dict) -> None:
    """Update an existing driver by Samsara ID (legacy method)."""
    _req("PATCH", f"/fleet/drivers/{_id}", json=patch)

def add_external_id_to_driver(driver_id: str, external_id_key: str, external_id_value: str) -> bool:
    """
    Add or update an external ID for an existing driver.

    Args:
        driver_id: Samsara driver ID
        external_id_key: The external ID key (e.g., "paycomname")
        external_id_value: The external ID value

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current driver data
        driver = _req("GET", f"/fleet/drivers/{driver_id}")

        # Update external IDs
        external_ids = driver.get("externalIds", {})
        external_ids[external_id_key] = external_id_value

        # Patch the driver
        patch_data = {"externalIds": external_ids}
        patch_driver(driver_id, patch_data)

        log.info(f"Added external ID {external_id_key}:{external_id_value} to driver {driver_id}")
        return True

    except Exception as e:
        log.error(f"Error adding external ID to driver {driver_id}: {e}")
        return False
