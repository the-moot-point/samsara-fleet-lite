# Samsara Driver Sync System - Usage Guide

## Overview
This system automatically processes new hires and terminations from OneDrive Excel reports and syncs them with Samsara's fleet management platform.

## Key Features
- **Auto-detection** of the latest report files from OneDrive
- **Username deduplication** to prevent conflicts
- **Batch processing** for both new hires and terminations
- **Dry-run mode** for testing without making changes
- **Comprehensive logging** and error handling

## Quick Start

Before running any commands, set the `SAMSARA_BEARER_TOKEN` environment variable.
The utilities will raise an `EnvironmentError` if it is missing.

### 1. Process Everything (Recommended)
```bash
# Process both terminations and new hires using latest files
python main.py process

# Test mode - preview changes without applying
python main.py process --dry-run
```

### 2. Process New Hires Only
```bash
# Use the latest New Hires Report automatically
python add_drivers.py

# Or specify a file manually
python add_drivers.py "C:\path\to\specific_file.xlsx"

# List available hire reports
python add_drivers.py --list

# Dry run to preview
python add_drivers.py --dry-run
```

### 3. Process Terminations Only
```bash
# Use the latest New Terms Report automatically
python deactivate_drivers.py

# Or specify a file manually
python deactivate_drivers.py "C:\path\to\specific_file.xlsx"

# List available termination reports
python deactivate_drivers.py --list

# Check if a specific person exists
python deactivate_drivers.py check John Smith
```

## Main Commands

### Using `main.py` (Recommended)

```bash
# Full processing workflow
python main.py process

# Check system status
python main.py status

# Run system tests
python main.py test

# Username management
python main.py username sync           # Sync with Samsara
python main.py username stats          # Show statistics
python main.py username check John Smith  # Test username generation
```

### Individual Scripts

#### Add Drivers
```bash
python add_drivers.py [OPTIONS] [FILE]

Options:
  --dry-run        Preview without making changes
  --verbose, -v    Enable detailed logging
  --sync          Sync usernames before processing
  --list          List available report files
```

#### Deactivate Drivers
```bash
python deactivate_drivers.py [OPTIONS] [FILE]

Options:
  --dry-run        Preview without making changes
  --verbose, -v    Enable detailed logging
  --list          List available report files
```

#### Username Management
```bash
# Sync existing Samsara usernames to local CSV
python sync_usernames.py sync

# Check what username would be generated
python sync_usernames.py check John Smith

# Show username statistics
python sync_usernames.py stats

# Check sync status with Samsara
python sync_usernames.py status
```

## File Detection

The system automatically finds the most recent files based on their timestamps:

### New Hire Reports
- **Directory**: `C:\Users\Jonathan\OneDrive - JECOfsb\Flow\Hires`
- **Pattern**: `YYYYMMDDHHMMSS_New Hires Report_[hash]_.xlsx`
- **Example**: `20250805080410_New Hires Report_1612d253_.xlsx`

### Termination Reports
- **Directory**: `C:\Users\Jonathan\OneDrive - JECOfsb\Flow\Terms`
- **Pattern**: `YYYYMMDDHHMMSS_New Terms Report_[hash]_xlsx`
- **Example**: `20250805080206_New Terms Report_3086494f_xlsx`

The system:
1. Scans the directory for matching files
2. Extracts timestamps from filenames
3. Selects the most recent file
4. Shows the file age (e.g., "2.5 hours ago")

## Configuration

### Environment Variables (.env)
```bash
# Required
SAMSARA_BEARER_TOKEN=your_token_here
DEFAULT_DRIVER_PASSWORD=TempPass123!

# OneDrive directories (or use defaults)
HIRES_DIR=C:\Users\Jonathan\OneDrive - JECOfsb\Flow\Hires
TERMS_DIR=C:\Users\Jonathan\OneDrive - JECOfsb\Flow\Terms

# Optional
PAYCOM_DIR=data
LOG_FILE=driver_sync.log
```

### Required CSV Files (in `data/` directory)

1. **locations.csv** - Location to tag/timezone mapping
2. **positions.csv** - Position to tag mapping
3. **never_positions.csv** - Positions to exclude
4. **usernames.csv** - Auto-maintained username database

## Workflow Examples

### Daily Processing
```bash
# Run the complete workflow
python main.py process

# Output:
# ============================================================
# SAMSARA DRIVER SYNC - FULL PROCESS
# ============================================================
# Started at: 2025-08-05 09:30:00
#
# 📋 Step 1: Processing Terminations
# ----------------------------------------
# 📄 Using most recent report: 20250805080206_New Terms Report_3086494f_xlsx
#    Created: 1.5 hours ago
# ✅ Deactivated: John Smith (terminated 2025-08-04)
# ✅ Terminations processed successfully
#
# 📋 Step 2: Processing New Hires
# ----------------------------------------
# 📄 Using most recent report: 20250805080410_New Hires Report_1612d253_.xlsx
#    Created: 1.0 hours ago
# ✅ Added: Cody Biesenbach as 'cbiesenbach'
# ✅ New hires processed successfully
```

### Testing Changes
```bash
# Always test first!
python main.py process --dry-run --verbose

# Check individual operations
python add_drivers.py --dry-run
python deactivate_drivers.py --dry-run
```

### Troubleshooting
```bash
# Check system status
python main.py status

# Run system tests
python main.py test

# Check username conflicts
python sync_usernames.py status --verbose

# List available files
python add_drivers.py --list
python deactivate_drivers.py --list
```

## Username Handling

The system ensures unique usernames:

1. **Base generation**: First initial + last name (e.g., `jsmith`)
2. **Conflict resolution**: Appends numbers if taken (e.g., `jsmith2`, `jsmith3`)
3. **Persistence**: Stores all usernames in `usernames.csv`
4. **Sync**: Can sync with existing Samsara drivers

Example:
```
John Smith → jsmith
Jane Smith → jsmith2  (if jsmith exists)
Jack Smith → jsmith3  (if jsmith and jsmith2 exist)
```

## Error Handling

The system handles common issues:

- **Missing files**: Clear error messages with suggestions
- **Missing locations/positions**: Warnings but continues processing
- **API failures**: Exponential backoff retry
- **Duplicate usernames**: Automatic modification
- **File not found**: Shows available files with `--list`

## Best Practices

1. **Always run with `--dry-run` first** to preview changes
2. **Use `main.py process`** for the complete workflow
3. **Check `main.py status`** before processing to verify setup
4. **Keep mapping CSV files updated** as locations/positions change
5. **Run `username sync`** periodically to stay synchronized
6. **Process terminations before new hires** to free up usernames
7. **Review logs** for any warnings about missing position tags

## Scheduling (Optional)

To run automatically, create a Windows Task Scheduler task:

```batch
@echo off
cd C:\path\to\your\project
python main.py process >> sync_log.txt 2>&1
```

Schedule this to run daily after your OneDrive sync completes.
