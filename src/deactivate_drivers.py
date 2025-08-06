"""
Process employee terminations from payroll reports.
Deactivates drivers in Samsara based on termination data using external IDs.
"""
import typer
import logging
import re
from pathlib import Path
from typing import Optional, Dict, List
import pandas as pd
from file_finder import PayrollFileFinder, get_latest_term_file
from samsara_client import (
    get_all_drivers,
    patch_driver,
    get_driver_by_external_id,
    deactivate_driver_by_external_id
)

app = typer.Typer()

def read_terminations_xlsx(path: str) -> pd.DataFrame:
    """
    Read termination report Excel file.

    Adjust column names as needed based on your actual termination report format.
    """
    log = logging.getLogger(__name__)
    df = pd.read_excel(path, dtype=str)

    # Expected columns (adjust based on your actual report)
    expected_cols = ["Legal_Firstname", "Legal_Lastname", "Termination_Date", "Employee_Status", "Hire_Date"]

    # Check which columns exist (Hire_Date might not be in termination report)
    available_cols = []
    for col in expected_cols:
        if col in df.columns:
            available_cols.append(col)
        elif col == "Hire_Date":
            # Hire_Date is optional for terminations
            log.warning("Hire_Date not found in termination report - will use name-based fallback if needed")
        else:
            log.error(f"Required column missing: {col}")

    # Keep only available columns
    df = df[available_cols]

    # Convert dates
    df["Termination_Date"] = pd.to_datetime(df["Termination_Date"])
    if "Hire_Date" in df.columns:
        df["Hire_Date"] = pd.to_datetime(df["Hire_Date"])

    return df.reset_index(drop=True)


def generate_paycom_key(first: str, last: str, hire_date) -> str:
    """
    Generate the paycom key for external ID lookup.
    Must match the format used in transformer.py
    Format: firstname-lastname_MM-DD-YYYY
    Example: John-Smith_01-15-2024

    Args:
        first: First name
        last: Last name
        hire_date: Hire date (pandas datetime or None)

    Returns:
        URL-safe paycom key
    """
    # Remove special characters and spaces, keep only alphanumeric
    first_clean = re.sub(r"[^a-zA-Z0-9]", "", first)
    last_clean = re.sub(r"[^a-zA-Z0-9]", "", last)

    # Format date as MM-DD-YYYY (matching Paycom format)
    if pd.notna(hire_date):
        date_str = hire_date.strftime("%m-%d-%Y")
        return f"{first_clean}-{last_clean}_{date_str}"
    else:
        # No hire date available - return None to signal fallback needed
        return None


def find_driver_by_name(drivers: List[Dict], first_name: str, last_name: str) -> Optional[Dict]:
    """
    Legacy: Find a driver in Samsara by name.
    Used as fallback when external ID lookup fails.

    Args:
        drivers: List of driver dictionaries from Samsara
        first_name: First name to search
        last_name: Last name to search

    Returns:
        Driver dictionary if found, None otherwise
    """
    full_name = f"{first_name} {last_name}".lower()

    for driver in drivers:
        if "name" in driver:
            driver_name = driver["name"].lower()
            if driver_name == full_name:
                return driver

    # Try alternative formats
    alt_name = f"{last_name}, {first_name}".lower()
    for driver in drivers:
        if "name" in driver:
            driver_name = driver["name"].lower()
            if driver_name == alt_name:
                return driver

    return None


@app.command()
def main(
    file: Optional[str] = typer.Argument(None, help="Path to termination Excel file. If not provided, uses latest from OneDrive"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without making API calls"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    list_files: bool = typer.Option(False, "--list", help="List available termination files and exit"),
    fallback: bool = typer.Option(True, "--fallback/--no-fallback", help="Use name matching as fallback when external ID not found")
):
    """
    Deactivate drivers in Samsara based on termination report.

    Uses external ID (paycomname) for reliable matching. If hire date is not available
    in the termination report, falls back to name matching (if --fallback is enabled).
    """
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    log = logging.getLogger(__name__)
    global log

    # List available files if requested
    if list_files:
        finder = PayrollFileFinder()
        reports = finder.list_all_reports("terms")

        if "term_reports" in reports and reports["term_reports"]:
            typer.echo("\n📁 Available Termination Reports:")
            typer.echo("=" * 60)
            for report in reports["term_reports"][:10]:  # Show max 10 most recent
                age = report.get("age_hours", 0)
                age_str = f"{age:.1f} hours ago" if age < 48 else f"{age/24:.1f} days ago"
                typer.echo(f"  • {report['name']}")
                typer.echo(f"    Created: {age_str}")

            if len(reports["term_reports"]) > 10:
                typer.echo(f"\n  ... and {len(reports['term_reports']) - 10} more older files")
        else:
            typer.echo("❌ No Termination Reports found in the configured directory")
        return

    # Determine which file to process
    if file:
        # Use the specified file
        file_path = Path(file)
        if not file_path.exists():
            typer.echo(f"❌ File not found: {file}", err=True)
            raise typer.Exit(1)
        log.info(f"Using specified file: {file_path}")
    else:
        # Find the most recent file
        try:
            file_path = get_latest_term_file()
            typer.echo(f"📄 Using most recent report: {file_path.name}")

            # Show file age
            finder = PayrollFileFinder()
            info = finder.get_file_info(file_path)
            if "age_hours" in info:
                age = info["age_hours"]
                if age < 1:
                    typer.echo(f"   Created: {int(age * 60)} minutes ago")
                elif age < 48:
                    typer.echo(f"   Created: {age:.1f} hours ago")
                else:
                    typer.echo(f"   Created: {age/24:.1f} days ago")
        except FileNotFoundError as e:
            typer.echo(f"❌ {e}", err=True)
            typer.echo("💡 Tip: Check your TERMS_DIR setting or specify a file manually")
            raise typer.Exit(1)

    # Read termination file
    log.info(f"Reading termination file: {file_path}")
    try:
        df = read_terminations_xlsx(str(file_path))
    except Exception as e:
        typer.echo(f"❌ Error reading Excel file: {e}", err=True)
        raise typer.Exit(1)

    log.info(f"Found {len(df)} terminations to process")

    # Check if we have hire dates
    has_hire_dates = "Hire_Date" in df.columns
    if not has_hire_dates:
        log.warning("⚠️  No Hire_Date column in termination report - external ID lookup may fail")
        if fallback:
            log.info("Will use name-based fallback when needed")
        else:
            log.warning("Fallback disabled - some terminations may not be processed")

    # Get all active drivers for fallback (if needed)
    active_drivers = []
    if fallback and not has_hire_dates:
        log.info("Fetching active drivers from Samsara for fallback matching...")
        active_drivers = get_all_drivers(include_deactivated=False)
        log.info(f"Found {len(active_drivers)} active drivers in Samsara")

    # Track statistics
    stats = {
        "total": len(df),
        "deactivated": 0,
        "not_found": 0,
        "already_deactivated": 0,
        "failed": 0,
        "used_fallback": 0,
        "not_found_details": []
    }

    # Process each termination
    for idx, row in df.iterrows():
        first_name = row.Legal_Firstname
        last_name = row.Legal_Lastname
        term_date = row.Termination_Date
        hire_date = row.get("Hire_Date") if has_hire_dates else None

        try:
            # Generate paycom key for external ID lookup
            paycom_key = generate_paycom_key(first_name, last_name, hire_date)

            driver_found = False
            used_fallback = False

            # Try external ID lookup first
            if paycom_key:
                log.debug(f"Looking up driver with paycomname: {paycom_key}")

                if dry_run:
                    # In dry run, check if driver exists
                    driver = get_driver_by_external_id("paycomname", paycom_key)
                    if driver:
                        driver_found = True
                        status = driver.get("driverActivationStatus", "active")
                        if status == "deactivated":
                            log.info(f"Already deactivated: {first_name} {last_name}")
                            stats["already_deactivated"] += 1
                        else:
                            log.info(f"[DRY RUN] Would deactivate: {first_name} {last_name} (terminated {term_date:%Y-%m-%d})")
                            stats["deactivated"] += 1
                else:
                    # Actually deactivate the driver
                    success = deactivate_driver_by_external_id(
                        "paycomname",
                        paycom_key,
                        term_date.strftime("%m-%d-%Y")
                    )
                    if success:
                        log.info(f"✅ Deactivated: {first_name} {last_name} (terminated {term_date:%Y-%m-%d})")
                        stats["deactivated"] += 1
                        driver_found = True

            # Fallback to name matching if external ID failed
            if not driver_found and fallback:
                log.info(f"External ID lookup failed for {first_name} {last_name}, trying name-based fallback")

                # Need to fetch drivers if not already done
                if not active_drivers:
                    active_drivers = get_all_drivers(include_deactivated=False)

                driver = find_driver_by_name(active_drivers, first_name, last_name)

                if driver:
                    driver_id = driver["id"]
                    driver_name = driver["name"]
                    used_fallback = True
                    stats["used_fallback"] += 1

                    # Check if already deactivated
                    if driver.get("driverActivationStatus") == "deactivated":
                        log.info(f"Already deactivated: {driver_name}")
                        stats["already_deactivated"] += 1
                    elif dry_run:
                        log.info(f"[DRY RUN] Would deactivate (via fallback): {driver_name} (terminated {term_date:%Y-%m-%d})")
                        stats["deactivated"] += 1
                    else:
                        # Deactivate using driver ID
                        patch_data = {
                            "driverActivationStatus": "deactivated",
                            "notes": f"Terminated: {term_date:%m-%d-%Y}"
                        }
                        patch_driver(driver_id, patch_data)
                        log.info(f"✅ Deactivated (via fallback): {driver_name} (terminated {term_date:%Y-%m-%d})")
                        stats["deactivated"] += 1

                        # Try to add the external ID for future use
                        if paycom_key:
                            from samsara_client import add_external_id_to_driver
                            add_external_id_to_driver(driver_id, "paycomname", paycom_key)
                            log.info(f"Added paycomname external ID for future reference")

                    driver_found = True

            # If still not found
            if not driver_found:
                log.warning(f"Driver not found: {first_name} {last_name}")
                stats["not_found"] += 1
                stats["not_found_details"].append({
                    "name": f"{first_name} {last_name}",
                    "paycom_key": paycom_key or "N/A (no hire date)",
                    "reason": "No hire date" if not paycom_key else "Not in Samsara"
                })

        except Exception as exc:
            log.error(f"❌ Failed to deactivate {first_name} {last_name}: {exc}")
            stats["failed"] += 1
            if verbose:
                log.exception("Full error details:")

    # Print summary
    typer.echo("\n" + "="*50)
    typer.echo("TERMINATION PROCESSING SUMMARY")
    typer.echo("="*50)
    typer.echo(f"File processed: {file_path.name}")
    typer.echo(f"Total terminations: {stats['total']}")
    if not dry_run:
        typer.echo(f"Successfully deactivated: {stats['deactivated']}")
    typer.echo(f"Not found in Samsara: {stats['not_found']}")
    typer.echo(f"Already deactivated: {stats['already_deactivated']}")
    typer.echo(f"Failed: {stats['failed']}")

    if stats["used_fallback"] > 0:
        typer.echo(f"Used name-based fallback: {stats['used_fallback']}")

    if stats["not_found_details"]:
        typer.echo(f"\nDrivers not found ({len(stats['not_found_details'])}):")
        for detail in stats["not_found_details"][:10]:  # Show max 10
            typer.echo(f"  • {detail['name']}")
            typer.echo(f"    Paycom key: {detail['paycom_key']}")
            typer.echo(f"    Reason: {detail['reason']}")
        if len(stats["not_found_details"]) > 10:
            typer.echo(f"  ... and {len(stats['not_found_details']) - 10} more")

    if dry_run:
        typer.echo("\n⚠️  This was a DRY RUN. No changes were made to Samsara.")

    # Exit with error code if any failures
    if stats["failed"] > 0:
        raise typer.Exit(1)


@app.command()
def check(
    first: str = typer.Argument(..., help="First name"),
    last: str = typer.Argument(..., help="Last name"),
    hire_date: Optional[str] = typer.Option(None, "--hire-date", help="Hire date in MM-DD-YYYY format")
):
    """
    Check if a specific driver exists in Samsara by external ID or name.
    """
    typer.echo(f"Searching for: {first} {last}")

    # Try external ID first if hire date provided
    if hire_date:
        try:
            hire_dt = pd.to_datetime(hire_date, format="%m-%d-%Y")
            paycom_key = generate_paycom_key(first, last, hire_dt)
            typer.echo(f"Checking external ID: paycomname:{paycom_key}")

            driver = get_driver_by_external_id("paycomname", paycom_key)
            if driver:
                status = driver.get("driverActivationStatus", "active")
                username = driver.get("username", "N/A")
                driver_id = driver.get("id", "N/A")

                typer.echo(f"✅ Found via external ID: {driver['name']}")
                typer.echo(f"   Status: {status}")
                typer.echo(f"   Username: {username}")
                typer.echo(f"   ID: {driver_id}")
                typer.echo(f"   External IDs: {driver.get('externalIds', {})}")
                return
        except Exception as e:
            typer.echo(f"Error with external ID lookup: {e}")

    # Fallback to name search
    typer.echo("Trying name-based search...")
    drivers = get_all_drivers(include_deactivated=True)
    driver = find_driver_by_name(drivers, first, last)

    if driver:
        status = driver.get("driverActivationStatus", "active")
        username = driver.get("username", "N/A")
        driver_id = driver.get("id", "N/A")

        typer.echo(f"✅ Found via name: {driver['name']}")
        typer.echo(f"   Status: {status}")
        typer.echo(f"   Username: {username}")
        typer.echo(f"   ID: {driver_id}")
        typer.echo(f"   External IDs: {driver.get('externalIds', {})}")

        if not hire_date:
            typer.echo("\n💡 Tip: Provide --hire-date to test external ID lookup")
    else:
        typer.echo(f"❌ Not found: {first} {last}")
        if hire_date:
            paycom_key = generate_paycom_key(first, last, pd.to_datetime(hire_date, format="%m-%d-%Y"))
            typer.echo(f"   Searched for external ID: paycomname:{paycom_key}")


if __name__ == "__main__":
    app()
