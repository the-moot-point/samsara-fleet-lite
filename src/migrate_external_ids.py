"""
Migration utility to add paycomname external IDs to existing drivers.
Run this once to backfill all drivers that were created before the external ID system.
"""

import typer
import logging
import re
from typing import Optional, Dict, List
from datetime import datetime
import pandas as pd
from pathlib import Path

app = typer.Typer()


@app.command()
def backfill_external_ids(
    dry_run: bool = typer.Option(
        True, "--dry-run/--execute", help="Preview changes without making API calls"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    hire_report: Optional[str] = typer.Option(
        None, "--hire-report", help="Path to a hire report with employee data"
    ),
    manual_csv: Optional[str] = typer.Option(
        None,
        "--csv",
        help="Path to CSV with columns: name, hire_date (MM-DD-YYYY format)",
    ),
):
    """
    Add paycomname external IDs to existing Samsara drivers.

    This migration tool helps transition existing drivers to use the new external ID system.
    You can provide employee data via:
    1. A recent hire report Excel file (--hire-report)
    2. A CSV file with name and hire_date columns (--csv, dates in MM-DD-YYYY format)
    3. Manual entry for individual drivers
    """
    from samsara_client import get_all_drivers, add_external_id_to_driver

    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger(__name__)

    typer.echo("\n" + "=" * 60)
    typer.echo("EXTERNAL ID MIGRATION TOOL")
    typer.echo("=" * 60)

    # Get all drivers from Samsara
    log.info("Fetching all drivers from Samsara...")
    all_drivers = get_all_drivers(include_deactivated=True)
    log.info(f"Found {len(all_drivers)} total drivers")

    # Filter drivers that need external IDs
    drivers_needing_ids = []
    drivers_with_ids = []

    for driver in all_drivers:
        external_ids = driver.get("externalIds", {})
        if "paycomname" not in external_ids:
            drivers_needing_ids.append(driver)
        else:
            drivers_with_ids.append(driver)

    typer.echo(f"\n📊 Current Status:")
    typer.echo(f"   Drivers with paycomname ID: {len(drivers_with_ids)}")
    typer.echo(f"   Drivers needing paycomname ID: {len(drivers_needing_ids)}")

    if not drivers_needing_ids:
        typer.echo("\n✅ All drivers already have paycomname external IDs!")
        return

    # Load employee data if provided
    employee_data = {}

    if hire_report:
        # Load from hire report Excel
        typer.echo(f"\n📄 Loading employee data from: {hire_report}")
        try:
            from payroll_reader import read_xlsx

            df = read_xlsx(hire_report)
            for _, row in df.iterrows():
                full_name = f"{row.Legal_Firstname} {row.Legal_Lastname}"
                employee_data[full_name.lower()] = {
                    "first": row.Legal_Firstname,
                    "last": row.Legal_Lastname,
                    "hire_date": row.Hire_Date,
                }
            typer.echo(f"   Loaded {len(employee_data)} employee records")
        except Exception as e:
            typer.echo(f"   ❌ Error loading hire report: {e}")

    elif manual_csv:
        # Load from CSV
        typer.echo(f"\n📄 Loading employee data from: {manual_csv}")
        try:
            df = pd.read_csv(manual_csv)
            if "name" in df.columns and "hire_date" in df.columns:
                # Parse hire_date with MM-DD-YYYY format
                df["hire_date"] = pd.to_datetime(df["hire_date"], format="%m-%d-%Y")
                for _, row in df.iterrows():
                    name_parts = row["name"].split(" ", 1)
                    if len(name_parts) == 2:
                        employee_data[row["name"].lower()] = {
                            "first": name_parts[0],
                            "last": name_parts[1],
                            "hire_date": row["hire_date"],
                        }
                typer.echo(f"   Loaded {len(employee_data)} employee records")
            else:
                typer.echo("   ❌ CSV must have 'name' and 'hire_date' columns")
        except Exception as e:
            typer.echo(f"   ❌ Error loading CSV: {e}")

    # Process drivers
    stats = {"updated": 0, "skipped": 0, "failed": 0, "no_hire_date": []}

    typer.echo(f"\n🔄 Processing {len(drivers_needing_ids)} drivers...")

    for driver in drivers_needing_ids:
        driver_id = driver["id"]
        driver_name = driver.get("name", "Unknown")

        # Try to find employee data
        employee_info = employee_data.get(driver_name.lower())

        if not employee_info:
            # Try to parse from driver notes if they contain hire date
            notes = driver.get("notes", "")
            hire_date_match = re.search(r"Hire Date: (\d{2}-\d{2}-\d{4})", notes)

            if hire_date_match:
                # Parse hire date from notes
                hire_date_str = hire_date_match.group(1)
                try:
                    hire_date = pd.to_datetime(hire_date_str, format="%m-%d-%Y")
                    name_parts = driver_name.split(" ", 1)
                    if len(name_parts) == 2:
                        employee_info = {
                            "first": name_parts[0],
                            "last": name_parts[1],
                            "hire_date": hire_date,
                        }
                        log.debug(f"Extracted hire date from notes for {driver_name}")
                except:
                    pass

        if employee_info:
            # Generate paycom key
            first_clean = re.sub(r"[^a-zA-Z0-9]", "", employee_info["first"])
            last_clean = re.sub(r"[^a-zA-Z0-9]", "", employee_info["last"])
            date_str = employee_info["hire_date"].strftime("%m-%d-%Y")
            paycom_key = f"{first_clean}_{last_clean}_{date_str}"

            if dry_run:
                log.info(
                    f"[DRY RUN] Would add paycomname:{paycom_key} to {driver_name}"
                )
                stats["updated"] += 1
            else:
                # Actually add the external ID
                success = add_external_id_to_driver(driver_id, "paycomname", paycom_key)
                if success:
                    log.info(f"✅ Added paycomname:{paycom_key} to {driver_name}")
                    stats["updated"] += 1
                else:
                    log.error(f"❌ Failed to update {driver_name}")
                    stats["failed"] += 1
        else:
            log.warning(f"⚠️  No hire date found for {driver_name}")
            stats["no_hire_date"].append(driver_name)
            stats["skipped"] += 1

    # Print summary
    typer.echo("\n" + "=" * 50)
    typer.echo("MIGRATION SUMMARY")
    typer.echo("=" * 50)

    if dry_run:
        typer.echo(f"Would update: {stats['updated']} drivers")
    else:
        typer.echo(f"Successfully updated: {stats['updated']} drivers")

    typer.echo(f"Skipped (no hire date): {stats['skipped']} drivers")
    typer.echo(f"Failed: {stats['failed']} drivers")

    if stats["no_hire_date"]:
        typer.echo(f"\n⚠️  Drivers without hire dates ({len(stats['no_hire_date'])}):")
        for name in stats["no_hire_date"][:10]:
            typer.echo(f"   • {name}")
        if len(stats["no_hire_date"]) > 10:
            typer.echo(f"   ... and {len(stats['no_hire_date']) - 10} more")

        typer.echo("\n💡 To add external IDs for these drivers:")
        typer.echo("   1. Create a CSV with columns: name, hire_date")
        typer.echo("   2. Format dates as MM-DD-YYYY")
        typer.echo(
            "   3. Run: python migrate_external_ids.py backfill-external-ids --csv your_file.csv"
        )

    if dry_run:
        typer.echo("\n⚠️  This was a DRY RUN. Run with --execute to apply changes.")


@app.command()
def verify(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    )
):
    """
    Verify the external ID coverage for all drivers.
    """
    from samsara_client import get_all_drivers

    typer.echo("\n🔍 Verifying External ID Coverage...")

    # Get all drivers
    all_drivers = get_all_drivers(include_deactivated=True)

    # Analyze external IDs
    with_paycom = []
    without_paycom = []
    with_other_ids = []

    for driver in all_drivers:
        external_ids = driver.get("externalIds", {})
        if "paycomname" in external_ids:
            with_paycom.append(driver)
        else:
            without_paycom.append(driver)

        if external_ids and "paycomname" not in external_ids:
            with_other_ids.append(driver)

    # Print statistics
    typer.echo(f"\n📊 External ID Statistics:")
    typer.echo(f"   Total drivers: {len(all_drivers)}")
    typer.echo(
        f"   With paycomname ID: {len(with_paycom)} ({len(with_paycom)*100/len(all_drivers):.1f}%)"
    )
    typer.echo(
        f"   Without paycomname ID: {len(without_paycom)} ({len(without_paycom)*100/len(all_drivers):.1f}%)"
    )
    typer.echo(f"   With other external IDs only: {len(with_other_ids)}")

    if verbose and without_paycom:
        typer.echo(f"\n❌ Drivers missing paycomname ID:")
        for driver in without_paycom[:20]:
            status = driver.get("driverActivationStatus", "active")
            typer.echo(f"   • {driver.get('name', 'Unknown')} ({status})")
            if driver.get("externalIds"):
                typer.echo(f"     Has IDs: {list(driver['externalIds'].keys())}")
        if len(without_paycom) > 20:
            typer.echo(f"   ... and {len(without_paycom) - 20} more")

    if verbose and with_paycom:
        typer.echo(f"\n✅ Sample of drivers with paycomname ID:")
        for driver in with_paycom[:5]:
            paycom_id = driver["externalIds"]["paycomname"]
            typer.echo(f"   • {driver.get('name', 'Unknown')}: {paycom_id}")


@app.command()
def add_single(
    first: str = typer.Argument(..., help="First name"),
    last: str = typer.Argument(..., help="Last name"),
    hire_date: str = typer.Argument(..., help="Hire date in MM-DD-YYYY format"),
    dry_run: bool = typer.Option(
        True, "--dry-run/--execute", help="Preview without making changes"
    ),
):
    """
    Add external ID for a single driver.
    """
    from samsara_client import get_all_drivers, add_external_id_to_driver
    import pandas as pd

    # Parse hire date
    try:
        hire_dt = pd.to_datetime(hire_date, format="%m-%d-%Y")
    except:
        typer.echo(f"❌ Invalid date format. Use MM-DD-YYYY")
        raise typer.Exit(1)

    # Generate paycom key
    first_clean = re.sub(r"[^a-zA-Z0-9]", "", first)
    last_clean = re.sub(r"[^a-zA-Z0-9]", "", last)
    date_str = hire_dt.strftime("%m-%d-%Y")
    paycom_key = f"{first_clean}_{last_clean}_{date_str}"

    typer.echo(f"Looking for driver: {first} {last}")
    typer.echo(f"Will add external ID: paycomname:{paycom_key}")

    # Find the driver
    all_drivers = get_all_drivers(include_deactivated=True)
    full_name = f"{first} {last}".lower()

    driver_found = None
    for driver in all_drivers:
        if driver.get("name", "").lower() == full_name:
            driver_found = driver
            break

    if not driver_found:
        typer.echo(f"❌ Driver not found: {first} {last}")
        raise typer.Exit(1)

    # Check existing external IDs
    existing_ids = driver_found.get("externalIds", {})
    if "paycomname" in existing_ids:
        typer.echo(f"⚠️  Driver already has paycomname: {existing_ids['paycomname']}")
        if not typer.confirm("Do you want to update it?"):
            raise typer.Exit(0)

    if dry_run:
        typer.echo(
            f"[DRY RUN] Would add paycomname:{paycom_key} to {driver_found['name']}"
        )
    else:
        success = add_external_id_to_driver(
            driver_found["id"], "paycomname", paycom_key
        )
        if success:
            typer.echo(
                f"✅ Successfully added paycomname:{paycom_key} to {driver_found['name']}"
            )
        else:
            typer.echo(f"❌ Failed to add external ID")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
