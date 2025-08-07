"""
Sync existing Samsara driver usernames to local CSV file.
Run this initially to populate usernames.csv with all existing drivers.
"""

import typer
import logging
from pathlib import Path
from .samsara_client import get_all_drivers, get_driver_usernames
from .username_manager import get_username_manager

app = typer.Typer()


@app.command()
def status(
    csv_path: str = typer.Option(None, "--csv", help="Path to usernames.csv file"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed breakdown"
    ),
):
    """
    Show the activation status of all usernames in Samsara.
    Compares local CSV with active/deactivated drivers in Samsara.
    """
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    # Get local usernames
    manager = get_username_manager(Path(csv_path) if csv_path else None)
    local_usernames = manager.get_all_usernames()

    # Get Samsara usernames with status
    typer.echo("Fetching driver status from Samsara...")
    samsara_status = get_driver_usernames(include_deactivated=True)

    # Analyze the data
    active_usernames = {u for u, s in samsara_status.items() if s == "active"}
    deactivated_usernames = {u for u, s in samsara_status.items() if s == "deactivated"}

    # Find discrepancies
    in_csv_not_samsara = local_usernames - set(samsara_status.keys())
    in_samsara_not_csv = set(samsara_status.keys()) - local_usernames

    # Display results
    typer.echo("\n" + "=" * 50)
    typer.echo("USERNAME STATUS REPORT")
    typer.echo("=" * 50)
    typer.echo(f"\n📁 Local CSV: {len(local_usernames)} usernames")
    typer.echo(f"☁️  Samsara Total: {len(samsara_status)} usernames")
    typer.echo(f"   ✅ Active: {len(active_usernames)}")
    typer.echo(f"   ⏸️  Deactivated: {len(deactivated_usernames)}")

    if in_csv_not_samsara:
        typer.echo(f"\n⚠️  In CSV but not in Samsara: {len(in_csv_not_samsara)}")
        if verbose and len(in_csv_not_samsara) <= 20:
            for username in sorted(in_csv_not_samsara):
                typer.echo(f"   - {username}")

    if in_samsara_not_csv:
        typer.echo(f"\n⚠️  In Samsara but not in CSV: {len(in_samsara_not_csv)}")
        if verbose and len(in_samsara_not_csv) <= 20:
            for username in sorted(in_samsara_not_csv):
                driver_status = samsara_status[username]
                typer.echo(f"   - {username} ({driver_status})")
        typer.echo("\n💡 Tip: Run 'sync' command to add these to your local CSV")

    if not in_csv_not_samsara and not in_samsara_not_csv:
        typer.echo("\n✅ Perfect sync! Local CSV matches Samsara completely.")


@app.command()
def sync(
    csv_path: str = typer.Option(None, "--csv", help="Path to usernames.csv file"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """
    Sync existing Samsara driver usernames to local CSV file.

    This should be run initially to populate the username database,
    and can be run periodically to ensure synchronization.
    """
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger(__name__)

    try:
        # Initialize username manager
        manager = get_username_manager(Path(csv_path) if csv_path else None)

        # Get current usernames from CSV
        existing_local = manager.get_all_usernames()
        log.info(f"Found {len(existing_local)} usernames in local CSV")

        # Fetch all drivers from Samsara (including deactivated)
        log.info("Fetching all drivers from Samsara API (active and deactivated)...")
        drivers = get_all_drivers(include_deactivated=True)
        log.info(f"Found {len(drivers)} total drivers in Samsara")

        # Extract usernames from drivers
        samsara_usernames = set()
        active_count = 0
        deactivated_count = 0

        for driver in drivers:
            if "username" in driver and driver["username"]:
                samsara_usernames.add(driver["username"])
                # Track status if available
                if "driverActivationStatus" in driver:
                    if driver["driverActivationStatus"] == "deactivated":
                        deactivated_count += 1
                    else:
                        active_count += 1

        log.info(f"Found {len(samsara_usernames)} usernames in Samsara")
        if active_count > 0 or deactivated_count > 0:
            log.info(f"  Active: {active_count}, Deactivated: {deactivated_count}")

        # Find new usernames not in local CSV
        new_usernames = samsara_usernames - existing_local
        if new_usernames:
            log.info(f"Adding {len(new_usernames)} new usernames to local CSV")
            if verbose:
                for username in sorted(new_usernames):
                    log.debug(f"  Adding: {username}")

            # Sync with manager
            manager.sync_with_samsara(samsara_usernames)

            typer.echo(
                f"✅ Successfully synced! Added {len(new_usernames)} new usernames."
            )
        else:
            typer.echo("✅ Already in sync! No new usernames to add.")

        # Report final status
        final_count = len(manager.get_all_usernames())
        typer.echo(f"Total usernames in database: {final_count}")

    except Exception as e:
        log.error(f"Sync failed: {e}")
        typer.echo(f"❌ Sync failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def check(
    first: str = typer.Argument(..., help="First name"),
    last: str = typer.Argument(..., help="Last name"),
    csv_path: str = typer.Option(None, "--csv", help="Path to usernames.csv file"),
):
    """
    Check what username would be generated for a given name.
    Useful for testing the deduplication logic.
    """
    import re

    # Initialize username manager
    manager = get_username_manager(Path(csv_path) if csv_path else None)

    # Generate base username
    base = re.sub(r"[^a-z0-9]", "", f"{first[0]}{last}".lower())

    # Check if it exists
    if manager.exists(base):
        typer.echo(f"Base username '{base}' already exists.")
        # Preview the unique username without modifying state
        test_unique = manager.check_available(base)
        typer.echo(f"Would generate: {test_unique}")
    else:
        typer.echo(f"Username '{base}' is available.")


@app.command()
def stats(
    csv_path: str = typer.Option(None, "--csv", help="Path to usernames.csv file")
):
    """
    Show statistics about the username database.
    """
    from collections import Counter

    # Initialize username manager
    manager = get_username_manager(Path(csv_path) if csv_path else None)
    usernames = manager.get_all_usernames()

    typer.echo(f"Total usernames: {len(usernames)}")

    # Find duplicates (usernames with numbers)
    duplicates = [u for u in usernames if any(c.isdigit() for c in u)]
    typer.echo(f"Modified usernames (with numbers): {len(duplicates)}")

    if duplicates and len(duplicates) <= 20:
        typer.echo("\nModified usernames:")
        for username in sorted(duplicates):
            typer.echo(f"  - {username}")

    # Find the most common base patterns
    bases = []
    for username in usernames:
        # Remove trailing digits to get base
        import re

        base = re.sub(r"\d+$", "", username)
        bases.append(base)

    counter = Counter(bases)
    most_common = counter.most_common(10)

    if len([c for c in counter.values() if c > 1]) > 0:
        typer.echo("\nMost duplicated base usernames:")
        for base, count in most_common:
            if count > 1:
                typer.echo(f"  - {base}: {count} variations")


if __name__ == "__main__":
    app()
