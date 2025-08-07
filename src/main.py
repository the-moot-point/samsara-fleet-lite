"""
Main CLI for Samsara Driver Sync System.
Combines all operations: add, deactivate, sync, migration, and utilities.
"""

import typer
from datetime import datetime

# Import command modules
from . import add_drivers
from . import deactivate_drivers
from . import sync_usernames
from . import migrate_external_ids
from .file_finder import PayrollFileFinder

app = typer.Typer(help="Samsara Driver Sync System")

# Add subcommands
app.add_typer(add_drivers.app, name="add", help="Add new drivers from hire reports")
app.add_typer(
    deactivate_drivers.app,
    name="deactivate",
    help="Deactivate drivers from termination reports",
)
app.add_typer(sync_usernames.app, name="username", help="Username management utilities")
app.add_typer(
    migrate_external_ids.app, name="migrate", help="External ID migration utilities"
)


@app.command()
def process(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without making API calls"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    update_existing: bool = typer.Option(
        False, "--update", help="Update/reactivate existing drivers"
    ),
):
    """
    Process both new hires and terminations using the latest reports.
    This is the main workflow that runs both operations in sequence.

    Now uses external IDs (paycomname) for reliable driver matching.
    """
    typer.echo("\n" + "=" * 60)
    typer.echo("SAMSARA DRIVER SYNC - FULL PROCESS")
    typer.echo("=" * 60)
    typer.echo(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Process terminations first (to free up usernames)
    typer.echo("📋 Step 1: Processing Terminations")
    typer.echo("-" * 40)
    try:
        deactivate_drivers.main(
            file=None,  # Use latest
            dry_run=dry_run,
            verbose=verbose,
            list_files=False,
            fallback=True,  # Use name fallback if needed
        )
        typer.echo("✅ Terminations processed successfully\n")
    except FileNotFoundError:
        typer.echo("⚠️  No termination reports found, skipping...\n")
    except Exception as e:
        typer.echo(f"❌ Error processing terminations: {e}\n")

    # Process new hires
    typer.echo("📋 Step 2: Processing New Hires")
    typer.echo("-" * 40)
    try:
        add_drivers.main(
            file=None,  # Use latest
            dry_run=dry_run,
            verbose=verbose,
            sync_first=True,  # Sync usernames before adding
            list_files=False,
            update_existing=update_existing,  # Update/reactivate if found
        )
        typer.echo("✅ New hires processed successfully\n")
    except FileNotFoundError:
        typer.echo("⚠️  No hire reports found, skipping...\n")
    except Exception as e:
        typer.echo(f"❌ Error processing new hires: {e}\n")

    typer.echo("=" * 60)
    typer.echo(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    typer.echo("=" * 60)


@app.command()
def status():
    """
    Show system status and available reports.
    """
    typer.echo("\n" + "=" * 60)
    typer.echo("SAMSARA DRIVER SYNC - SYSTEM STATUS")
    typer.echo("=" * 60)

    finder = PayrollFileFinder()

    # Check directories
    typer.echo("\n📁 Configured Directories:")
    typer.echo(f"  Hires: {finder.hires_dir}")
    typer.echo(
        f"         {'✅ Exists' if finder.hires_dir.exists() else '❌ Not found'}"
    )
    typer.echo(f"  Terms: {finder.terms_dir}")
    typer.echo(
        f"         {'✅ Exists' if finder.terms_dir.exists() else '❌ Not found'}"
    )

    # Show latest reports
    reports = finder.list_all_reports("both")

    typer.echo("\n📄 Latest Reports:")

    if "hire_reports" in reports and reports["hire_reports"]:
        latest_hire = reports["hire_reports"][0]
        age = latest_hire.get("age_hours", 0)
        age_str = f"{age:.1f} hours ago" if age < 48 else f"{age/24:.1f} days ago"
        typer.echo(f"  New Hires: {latest_hire['name']}")
        typer.echo(f"             Created {age_str}")
    else:
        typer.echo("  New Hires: No reports found")

    if "term_reports" in reports and reports["term_reports"]:
        latest_term = reports["term_reports"][0]
        age = latest_term.get("age_hours", 0)
        age_str = f"{age:.1f} hours ago" if age < 48 else f"{age/24:.1f} days ago"
        typer.echo(f"  Terms:     {latest_term['name']}")
        typer.echo(f"             Created {age_str}")
    else:
        typer.echo("  Terms:     No reports found")

    # Check username database
    from .username_manager import get_username_manager

    try:
        manager = get_username_manager()
        usernames = manager.get_all_usernames()
        typer.echo(f"\n👤 Username Database: {len(usernames)} registered usernames")

        # Check for duplicates
        duplicates = [u for u in usernames if any(c.isdigit() for c in u)]
        if duplicates:
            typer.echo(f"   Including {len(duplicates)} modified (with numbers)")
    except Exception as e:
        typer.echo(f"\n👤 Username Database: Error loading ({e})")

    # Check Samsara connection and external IDs
    typer.echo("\n🌐 Samsara API:")
    try:
        from .samsara_client import get_drivers_by_status

        active = get_drivers_by_status("active")
        deactivated = get_drivers_by_status("deactivated")
        typer.echo("   ✅ Connected")
        typer.echo(f"   Active drivers: {len(active)}")
        typer.echo(f"   Deactivated drivers: {len(deactivated)}")

        # Check external ID coverage
        all_drivers = active + deactivated
        with_external_id = sum(
            1 for d in all_drivers if "paycomname" in d.get("externalIds", {})
        )
        typer.echo("\n🔗 External ID Status:")
        typer.echo(
            f"   Drivers with paycomname ID: {with_external_id}/{len(all_drivers)} ({with_external_id*100/len(all_drivers):.1f}%)"
        )

        if with_external_id < len(all_drivers):
            typer.echo("   💡 Run 'migrate verify' to see details")
            typer.echo("   💡 Run 'migrate backfill-external-ids' to add missing IDs")

    except Exception as e:
        typer.echo(f"   ❌ Connection failed: {e}")

    typer.echo("")


@app.command()
def test():
    """
    Run a test to verify all components are working.
    """
    typer.echo("\n🧪 Running System Tests...")
    typer.echo("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Config loading
    typer.echo("\n1. Testing configuration...")
    try:
        from config import settings

        assert settings.api_token, "API token not set"
        typer.echo("   ✅ Configuration loaded")
        tests_passed += 1
    except Exception as e:
        typer.echo(f"   ❌ Configuration error: {e}")
        tests_failed += 1

    # Test 2: File directories
    typer.echo("\n2. Testing file directories...")
    try:
        finder = PayrollFileFinder()
        if finder.hires_dir.exists():
            typer.echo("   ✅ Hires directory exists")
            tests_passed += 1
        else:
            typer.echo(f"   ⚠️  Hires directory not found: {finder.hires_dir}")
            tests_failed += 1

        if finder.terms_dir.exists():
            typer.echo("   ✅ Terms directory exists")
            tests_passed += 1
        else:
            typer.echo(f"   ⚠️  Terms directory not found: {finder.terms_dir}")
            tests_failed += 1
    except Exception as e:
        typer.echo(f"   ❌ Directory error: {e}")
        tests_failed += 1

    # Test 3: Mapping files
    typer.echo("\n3. Testing mapping files...")
    try:
        from .mapping_loader import (
            load_position_tags,
            load_location_tags_and_timezones,
        )

        positions = load_position_tags()
        locations = load_location_tags_and_timezones()
        typer.echo(f"   ✅ Loaded {len(positions)} positions")
        typer.echo(f"   ✅ Loaded {len(locations)} locations")
        tests_passed += 2
    except Exception as e:
        typer.echo(f"   ❌ Mapping file error: {e}")
        tests_failed += 1

    # Test 4: Username manager
    typer.echo("\n4. Testing username manager...")
    try:
        from .username_manager import get_username_manager

        manager = get_username_manager()
        # Preview a username to ensure manager responds without modifying state
        _ = manager.check_available("testuser9999")
        typer.echo("   ✅ Username manager working")
        tests_passed += 1
    except Exception as e:
        typer.echo(f"   ❌ Username manager error: {e}")
        tests_failed += 1

    # Test 5: Samsara API
    typer.echo("\n5. Testing Samsara API connection...")
    try:
        from .samsara_client import get_drivers_by_status

        drivers = get_drivers_by_status("active")
        typer.echo(f"   ✅ API connected ({len(drivers)} active drivers)")
        tests_passed += 1
    except Exception as e:
        typer.echo(f"   ❌ API connection error: {e}")
        tests_failed += 1

    # Test 6: External ID support
    typer.echo("\n6. Testing external ID functions...")
    try:
        from .samsara_client import get_driver_by_external_id

        # Test with a non-existent ID (should return None, not error)
        result = get_driver_by_external_id("paycomname", "test_nonexistent_2099-01-01")
        if result is None:
            typer.echo("   ✅ External ID lookup working")
            tests_passed += 1
        else:
            typer.echo("   ⚠️  Unexpected result from external ID test")
            tests_failed += 1
    except Exception as e:
        typer.echo(f"   ❌ External ID error: {e}")
        tests_failed += 1

    # Summary
    typer.echo("\n" + "=" * 60)
    typer.echo(f"Test Results: {tests_passed} passed, {tests_failed} failed")
    if tests_failed == 0:
        typer.echo("✅ All systems operational!")
    else:
        typer.echo(f"⚠️  {tests_failed} test(s) failed. Check configuration.")
    typer.echo("=" * 60 + "\n")


@app.command()
def quickstart():
    """
    Interactive quickstart guide for new users.
    """
    typer.echo("\n" + "=" * 60)
    typer.echo("🚀 SAMSARA DRIVER SYNC - QUICKSTART GUIDE")
    typer.echo("=" * 60)

    typer.echo("\nWelcome! This guide will help you get started.\n")

    # Step 1: Check status
    typer.echo("Step 1: Let's check your system status...")
    if typer.confirm("Run status check?", default=True):
        status()

    # Step 2: Sync existing usernames
    typer.echo("\nStep 2: Sync existing Samsara usernames...")
    typer.echo("This ensures we don't create duplicate usernames.")
    if typer.confirm("Sync usernames from Samsara?", default=True):
        from .sync_usernames import sync

        sync(verbose=False)

    # Step 3: Check for drivers without external IDs
    typer.echo("\nStep 3: Check external ID coverage...")
    typer.echo("External IDs ensure reliable driver matching.")
    if typer.confirm("Check external ID status?", default=True):
        from .migrate_external_ids import verify

        verify(verbose=False)

        # Offer to migrate if needed
        typer.echo(
            "\nIf you have drivers without external IDs, you should migrate them."
        )
        if typer.confirm("Would you like to see migration options?"):
            typer.echo("\nMigration options:")
            typer.echo("1. If you have a recent hire report with all employees:")
            typer.echo(
                "   python main.py migrate backfill-external-ids --hire-report path/to/report.xlsx --execute"
            )
            typer.echo("\n2. For individual drivers:")
            typer.echo(
                "   python main.py migrate add-single John Smith 01-15-2024 --execute"
            )

    # Step 4: Process reports
    typer.echo("\nStep 4: Process payroll reports...")
    typer.echo("You can now process new hires and terminations.")
    typer.echo("\nCommon commands:")
    typer.echo("  • Dry run (preview): python main.py process --dry-run")
    typer.echo("  • Process all:       python main.py process")
    typer.echo("  • With updates:      python main.py process --update")
    typer.echo("  • Just new hires:    python main.py add")
    typer.echo("  • Just terminations: python main.py deactivate")

    typer.echo("\n✅ Setup complete! You're ready to sync drivers.")
    typer.echo("\n📚 For more help, check the README or run: python main.py --help")
    typer.echo("=" * 60 + "\n")


if __name__ == "__main__":
    app()
