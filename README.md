# Samsara Fleet Lite

A minimal SDK and CLI for syncing drivers with the Samsara Fleet Management API.
For full workflow details and advanced options, see the [Usage Guide](usage_guide.md).

## Installation

Install in editable mode with development dependencies:

```bash
pip install -e .[dev]
```

## Command Line Usage

Use the provided console scripts to preview changes with your report files:

```bash
add-drivers path/to/New_Hires.xlsx --dry-run
deactivate-drivers path/to/Terms.xlsx --dry-run
```

### Alternative invocation

If the console scripts are unavailable, call the modules directly:

```bash
PYTHONPATH=$PWD/src python -m src.add_drivers path/to/New_Hires.xlsx --dry-run
```

## Next steps

Read the [Usage Guide](usage_guide.md) for environment variables, batch processing,
and additional commands.
