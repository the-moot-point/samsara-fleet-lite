# External ID Implementation Guide

## Overview
The system now uses a composite external ID (`paycomname`) to create a reliable link between payroll records and Samsara driver records. This eliminates the fragile name-matching approach and ensures accurate driver updates and deactivations.

## External ID Format
- **Key**: `paycomname`
- **Value**: `FirstName-LastName_MM-DD-YYYY`
- **Example**: `John-Smith_01-15-2024`

The format is URL-safe with alphanumeric characters only, using a hyphen between the first and last name, an underscore before the hire date, and the hire date in MM-DD-YYYY format (matching Paycom's format).

## Key Changes Made

### 1. **transformer.py**
- Added `_generate_paycom_key()` function to create consistent external IDs
- Modified `row_to_payload()` to include `paycomname` in external IDs
- External ID is automatically added to all new drivers

### 2. **samsara_client.py**
Enhanced with external ID support:
- `get_driver_by_external_id()` - Find drivers using external ID
- `update_driver_by_external_id()` - Update drivers without knowing Samsara ID
- `deactivate_driver_by_external_id()` - Deactivate using external ID
- `add_external_id_to_driver()` - Add external IDs to existing drivers

### 3. **deactivate_drivers.py**
- Primary lookup via external ID (`paycomname`)
- Falls back to name matching if hire date unavailable
- Adds external ID during fallback for future use
- `--no-fallback` flag to disable name matching

### 4. **add_drivers.py**
- Checks for existing drivers via external ID before adding
- `--update` flag to reactivate deactivated drivers
- Updates existing active drivers with new information
- Prevents duplicate driver creation

### 5. **migrate_external_ids.py** (New)
Migration utilities for existing drivers:
- `backfill-external-ids` - Batch add external IDs
- `verify` - Check external ID coverage
- `add-single` - Add external ID for one driver

### 6. **main.py**
- Added migration commands
- Enhanced status to show external ID coverage
- New quickstart guide for onboarding
- Updated process command with `--update` flag

## Usage Guide

### Initial Setup (One-Time)
```bash
# 1. Check system status
python main.py status

# 2. Sync existing usernames
python main.py username sync

# 3. Check external ID coverage
python main.py migrate verify

# 4. Migrate existing drivers (if needed)
python main.py migrate backfill-external-ids --hire-report path/to/recent_report.xlsx --dry-run
python main.py migrate backfill-external-ids --hire-report path/to/recent_report.xlsx --execute
```

### Daily Operations

#### Process Everything (Recommended)
```bash
# Preview changes
python main.py process --dry-run

# Execute with updates/reactivations
python main.py process --update

# Execute without updates
python main.py process
```

#### Process Individual Reports
```bash
# Add new hires only
python main.py add --update

# Deactivate terminations only
python main.py deactivate

# List available files
python main.py add --list
python main.py deactivate --list
```

#### Check Individual Drivers
```bash
# Check if a driver exists
python main.py add check John Smith 01-15-2024

# Check termination lookup
python main.py deactivate check John Smith --hire-date 01-15-2024
```

### Migration Commands

#### Bulk Migration
```bash
# Using a hire report
python main.py migrate backfill-external-ids --hire-report report.xlsx --execute

# Using a custom CSV (columns: name, hire_date)
python main.py migrate backfill-external-ids --csv employees.csv --execute
```

#### Individual Migration
```bash
python main.py migrate add-single John Smith 01-15-2024 --execute
```

#### Verification
```bash
# Basic coverage stats
python main.py migrate verify

# Detailed information
python main.py migrate verify --verbose
```

## Benefits

1. **Reliability**: No more failed lookups due to name variations
2. **Immutability**: External ID remains constant even if names change
3. **Performance**: Direct API lookup instead of searching all drivers
4. **Auditability**: Clear link between payroll and Samsara records
5. **Flexibility**: Graceful fallback when hire dates unavailable

## Handling Edge Cases

### Missing Hire Dates in Termination Reports
If termination reports don't include hire dates:
1. System attempts external ID lookup first
2. Falls back to name matching (if enabled)
3. Adds external ID during fallback for future use
4. Use `--no-fallback` to disable name matching

### Duplicate Names
The composite key (name + hire date) handles most duplicates. For edge cases:
- System will process both employees correctly
- Each gets a unique username (e.g., jsmith, jsmith2)
- Each has a unique external ID due to different hire dates

### Name Changes
Original external ID is preserved, ensuring continuity. The system finds drivers by their original hiring information.

### Reactivations
When an employee is rehired:
- If same hire date: Driver is reactivated with `--update` flag
- If different hire date: New driver record created (different person or rehire)

## Troubleshooting

### Driver Not Found During Termination
```bash
# Check if driver exists
python main.py deactivate check FirstName LastName --hire-date MM-DD-YYYY

# If not found, verify the hire date matches exactly
# Or enable fallback: python main.py deactivate --fallback
```

### Duplicate Driver Created
```bash
# Check external ID coverage
python main.py migrate verify --verbose

# Find and fix duplicates manually, then add external ID
python main.py migrate add-single FirstName LastName MM-DD-YYYY --execute
```

### Migration Issues
```bash
# Extract hire dates from driver notes (if stored there)
python main.py migrate backfill-external-ids --dry-run

# Create manual CSV for missing data
echo "name,hire_date" > manual_fixes.csv
echo "John Smith,01-15-2024" >> manual_fixes.csv
python main.py migrate backfill-external-ids --csv manual_fixes.csv --execute
```

## Best Practices

1. **Always run dry-run first**: Preview changes before execution
2. **Regular verification**: Check external ID coverage weekly
3. **Use --update flag**: Reactivate/update existing drivers
4. **Monitor failed lookups**: Review logs for drivers not found
5. **Keep hire dates accurate**: Critical for external ID generation

## API Details

### Samsara External ID Format
- URL: `/fleet/drivers/{externalIdKey}:{externalIdValue}`
    - Encoded: `/fleet/drivers/paycomname%3AJohn-Smith_01-15-2024`
- Supports GET, PATCH, DELETE operations

### Example API Calls
```python
# Get driver
GET /fleet/drivers/paycomname%3AJohn-Smith_01-15-2024

# Update driver
PATCH /fleet/drivers/paycomname%3AJohn-Smith_01-15-2024
{
  "driverActivationStatus": "deactivated",
  "notes": "Terminated: 12-31-2024"
}

# The system handles all encoding automatically
```

## Next Steps

With the external ID system in place, consider:

1. **Automated Scheduling**: Set up cron jobs for daily processing
2. **Email Notifications**: Alert on processing results
3. **Audit Logging**: Track all driver changes
4. **Dashboard**: Web interface for monitoring
5. **Advanced Updates**: Sync more fields (phone, address, etc.)
6. **Batch Operations**: Process multiple files at once
7. **Error Recovery**: Automatic retry for failed operations

The external ID system provides a solid foundation for reliable, maintainable driver synchronization between your payroll system and Samsara.
