import typer
import logging
import json
from pathlib import Path
from typing import Optional
from .payroll_reader import read_xlsx
from .transformer import row_to_payload, _generate_paycom_key
from .samsara_client import (
    add_driver,
    get_driver_by_external_id,
    update_driver_by_external_id,
)
from .username_manager import get_username_manager
from .file_finder import PayrollFileFinder, get_latest_hire_file

app = typer.Typer()


@app.command()
def main(
    file: Optional[str] = typer.Argument(
        None, help="Path to Excel file. If not provided, uses latest from OneDrive"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without making API calls"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    sync_first: bool = typer.Option(
        False, "--sync", help="Sync with Samsara before processing"
    ),
    list_files: bool = typer.Option(
        False, "--list", help="List available report files and exit"
    ),
    update_existing: bool = typer.Option(
        False, "--update", help="Update existing drivers if found"
    ),
):
    """
    Add new drivers from payroll Excel file to Samsara.

    If no file is specified, automatically uses the most recent New Hires Report.
    Uses external IDs (paycomname) to check for existing drivers and avoid duplicates.
    """
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger(__name__)

    # List available files if requested
    if list_files:
        finder = PayrollFileFinder()
        reports = finder.list_all_reports("hires")

        if "hire_reports" in reports and reports["hire_reports"]:
            typer.echo("\n📁 Available New Hire Reports:")
            typer.echo("=" * 60)
            for report in reports["hire_reports"][:10]:  # Show max 10 most recent
                age = report.get("age_hours", 0)
                age_str = (
                    f"{age:.1f} hours ago" if age < 48 else f"{age / 24:.1f} days ago"
                )
                typer.echo(f"  • {report['name']}")
                typer.echo(f"    Created: {age_str}")

            if len(reports["hire_reports"]) > 10:
                typer.echo(
                    f"\n  ... and {len(reports['hire_reports']) - 10} more older files"
                )
        else:
            typer.echo("❌ No New Hire Reports found in the configured directory")
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
            file_path = get_latest_hire_file()
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
                    typer.echo(f"   Created: {age / 24:.1f} days ago")
        except FileNotFoundError as e:
            typer.echo(f"❌ {e}", err=True)
            typer.echo(
                "💡 Tip: Check your HIRES_DIR setting or specify a file manually"
            )
            raise typer.Exit(1)

    # Optionally sync existing usernames first
    if sync_first:
        log.info("Syncing existing Samsara usernames (active and deactivated)...")
        from .samsara_client import get_all_drivers

        manager = get_username_manager()
        drivers = get_all_drivers(include_deactivated=True)
        samsara_usernames = {
            d["username"] for d in drivers if "username" in d and d["username"]
        }
        manager.sync_with_samsara(samsara_usernames)
        log.info(f"Synced {len(samsara_usernames)} existing usernames")

    # Read Excel file
    log.info(f"Reading Excel file: {file_path}")
    try:
        df = read_xlsx(str(file_path))
    except Exception as e:
        typer.echo(f"❌ Error reading Excel file: {e}", err=True)
        raise typer.Exit(1)

    log.info(f"Found {len(df)} active employees to process")

    # Track statistics
    stats = {
        "total": len(df),
        "added": 0,
        "skipped": 0,
        "already_exists": 0,
        "updated": 0,
        "reactivated": 0,
        "failed": 0,
        "modified_usernames": [],
        "existing_drivers": [],
    }

    # Process each employee
    for idx, row in df.iterrows():
        try:
            # Check if driver already exists using external ID
            paycom_key = _generate_paycom_key(
                row.Legal_Firstname, row.Legal_Lastname, row.Hire_Date
            )

            existing_driver = get_driver_by_external_id("paycomname", paycom_key)

            if existing_driver:
                # Driver already exists
                driver_name = existing_driver.get(
                    "name", f"{row.Legal_Firstname} {row.Legal_Lastname}"
                )
                driver_status = existing_driver.get("driverActivationStatus", "active")

                stats["existing_drivers"].append(
                    {
                        "name": driver_name,
                        "status": driver_status,
                        "paycom_key": paycom_key,
                    }
                )

                if driver_status == "deactivated":
                    # Reactivate the driver
                    if update_existing:
                        if dry_run:
                            log.info(f"[DRY RUN] Would reactivate: {driver_name}")
                            stats["reactivated"] += 1
                        else:
                            # Reactivate the driver
                            update_data = {
                                "driverActivationStatus": "active",
                                "notes": f"Reactivated: {row.Hire_Date:%m-%d-%Y}",
                            }
                            success = update_driver_by_external_id(
                                "paycomname", paycom_key, update_data
                            )
                            if success:
                                log.info(f"✅ Reactivated: {driver_name}")
                                stats["reactivated"] += 1
                            else:
                                log.error(f"Failed to reactivate: {driver_name}")
                                stats["failed"] += 1
                    else:
                        log.info(
                            f"Driver exists but is deactivated: {driver_name} (use --update to reactivate)"
                        )
                        stats["already_exists"] += 1
                else:
                    # Driver is active, check if we should update
                    if update_existing:
                        # Generate new payload to get updated information
                        payload = row_to_payload(row)
                        if payload:
                            if dry_run:
                                log.info(f"[DRY RUN] Would update: {driver_name}")
                                stats["updated"] += 1
                            else:
                                # Update relevant fields (location, position, etc.)
                                update_data = {
                                    "tagIds": payload.tagIds,
                                    "timezone": payload.timezone,
                                    "licenseState": payload.licenseState,
                                    "notes": f"Updated: {row.Hire_Date:%m-%d-%Y}",
                                }
                                if payload.peerGroupTagId:
                                    update_data["peerGroupTagId"] = (
                                        payload.peerGroupTagId
                                    )

                                success = update_driver_by_external_id(
                                    "paycomname", paycom_key, update_data
                                )
                                if success:
                                    log.info(f"✅ Updated: {driver_name}")
                                    stats["updated"] += 1
                                else:
                                    log.error(f"Failed to update: {driver_name}")
                                    stats["failed"] += 1
                    else:
                        log.info(f"Driver already exists and is active: {driver_name}")
                        stats["already_exists"] += 1

                continue  # Skip to next employee

            # Driver doesn't exist, proceed with adding
            # Generate payload (includes username deduplication)
            payload = row_to_payload(row)

            if payload is None:
                log.info(
                    f"Skipped {row.Legal_Firstname} {row.Legal_Lastname} (excluded position)"
                )
                stats["skipped"] += 1
                continue

            # Check if username was modified
            import re

            base_username = re.sub(
                r"[^a-z0-9]",
                "",
                f"{row.Legal_Firstname[0]}{row.Legal_Lastname}".lower(),
            )
            if payload.username != base_username:
                stats["modified_usernames"].append(
                    {
                        "name": f"{row.Legal_Firstname} {row.Legal_Lastname}",
                        "original": base_username,
                        "modified": payload.username,
                    }
                )
                log.info(
                    f"Username modified: {row.Legal_Firstname} {row.Legal_Lastname} -> {payload.username}"
                )

            if dry_run:
                log.info(
                    f"[DRY RUN] Would add: {row.Legal_Firstname} {row.Legal_Lastname} as '{payload.username}'"
                )
                log.info(f"          External ID: paycomname:{paycom_key}")
                if verbose:
                    log.debug(
                        f"Payload: {json.dumps(payload.model_dump(exclude_none=True), indent=2)}"
                    )
                stats["added"] += 1
            else:
                # Actually add the driver
                add_driver(payload)
                log.info(
                    f"✅ Added: {row.Legal_Firstname} {row.Legal_Lastname} as '{payload.username}'"
                )
                log.info(f"   External ID: paycomname:{paycom_key}")
                stats["added"] += 1

        except Exception as exc:
            log.error(
                f"❌ Failed to process {row.Legal_Firstname} {row.Legal_Lastname}: {exc}"
            )
            stats["failed"] += 1
            if verbose:
                log.exception("Full error details:")

    # Print summary
    typer.echo("\n" + "=" * 50)
    typer.echo("SUMMARY")
    typer.echo("=" * 50)
    typer.echo(f"File processed: {file_path.name}")
    typer.echo(f"Total employees processed: {stats['total']}")

    if not dry_run:
        if stats["added"] > 0:
            typer.echo(f"✅ Successfully added: {stats['added']}")
        if stats["updated"] > 0:
            typer.echo(f"📝 Updated existing: {stats['updated']}")
        if stats["reactivated"] > 0:
            typer.echo(f"♻️  Reactivated: {stats['reactivated']}")
    else:
        if stats["added"] > 0:
            typer.echo(f"Would add: {stats['added']}")
        if stats["updated"] > 0:
            typer.echo(f"Would update: {stats['updated']}")
        if stats["reactivated"] > 0:
            typer.echo(f"Would reactivate: {stats['reactivated']}")

    if stats["already_exists"] > 0:
        typer.echo(f"Already exists: {stats['already_exists']}")
    if stats["skipped"] > 0:
        typer.echo(f"Skipped (excluded positions): {stats['skipped']}")
    if stats["failed"] > 0:
        typer.echo(f"❌ Failed: {stats['failed']}")

    if stats["existing_drivers"]:
        typer.echo(f"\n📋 Existing drivers found ({len(stats['existing_drivers'])}):")
        for item in stats["existing_drivers"][:10]:
            status_icon = "✅" if item["status"] == "active" else "⏸️"
            typer.echo(f"  {status_icon} {item['name']} ({item['status']})")
        if len(stats["existing_drivers"]) > 10:
            typer.echo(f"  ... and {len(stats['existing_drivers']) - 10} more")

        if not update_existing and any(
            d["status"] == "deactivated" for d in stats["existing_drivers"]
        ):
            typer.echo("\n💡 Tip: Use --update flag to reactivate deactivated drivers")

    if stats["modified_usernames"]:
        typer.echo(f"\nModified usernames ({len(stats['modified_usernames'])}):")
        for item in stats["modified_usernames"]:
            typer.echo(f"  • {item['name']}: {item['original']} → {item['modified']}")

    if dry_run:
        typer.echo("\n⚠️  This was a DRY RUN. No changes were made to Samsara.")

    # Exit with error code if any failures
    if stats["failed"] > 0:
        raise typer.Exit(1)


@app.command()
def check(
    first: str = typer.Argument(..., help="First name"),
    last: str = typer.Argument(..., help="Last name"),
    hire_date: str = typer.Argument(..., help="Hire date in MM-DD-YYYY format"),
):
    """
    Check if a driver would be added or already exists.
    """
    import pandas as pd

    # Parse hire date
    try:
        hire_dt = pd.to_datetime(hire_date, format="%m-%d-%Y")
    except ValueError:
        typer.echo("❌ Invalid date format. Use MM-DD-YYYY")
        raise typer.Exit(1)

    # Generate paycom key
    paycom_key = _generate_paycom_key(first, last, hire_dt)

    typer.echo(f"\n🔍 Checking: {first} {last}")
    typer.echo(f"   Hire Date: {hire_date}")
    typer.echo(f"   External ID: paycomname:{paycom_key}")

    # Check if driver exists
    existing_driver = get_driver_by_external_id("paycomname", paycom_key)

    if existing_driver:
        status = existing_driver.get("driverActivationStatus", "active")
        username = existing_driver.get("username", "N/A")
        driver_id = existing_driver.get("id", "N/A")

        status_icon = "✅" if status == "active" else "⏸️"
        typer.echo(f"\n{status_icon} Driver EXISTS in Samsara")
        typer.echo(f"   Name: {existing_driver.get('name', 'Unknown')}")
        typer.echo(f"   Status: {status}")
        typer.echo(f"   Username: {username}")
        typer.echo(f"   Driver ID: {driver_id}")
        typer.echo(f"   External IDs: {existing_driver.get('externalIds', {})}")

        if status == "deactivated":
            typer.echo(
                "\n💡 This driver is deactivated. Use --update flag when running 'add' to reactivate."
            )
    else:
        typer.echo("\n❌ Driver does NOT exist in Samsara")
        typer.echo("   This driver would be ADDED if processed.")

        # Check what username would be generated
        import re
        from .username_manager import get_username_manager

        manager = get_username_manager()
        base_username = re.sub(r"[^a-z0-9]", "", f"{first[0]}{last}".lower())

        if manager.exists(base_username):
            typer.echo(f"\n⚠️  Username '{base_username}' already exists")
            typer.echo("   A modified username would be generated")


if __name__ == "__main__":
    app()
