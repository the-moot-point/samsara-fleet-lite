# AGENTS.md — samsara‑fleet‑lite

## Project summary
This repo is a slim Python SDK for interacting with the Samsara Fleet Management
API.  Key entry‑points live under `src/`:

| Area | Module | Notes |
|------|--------|-------|
| Models & DTOs | `models.py` | Pydantic models mirroring Samsara objects |
| API wrapper   | `src/client.py` | Thin `requests` wrapper w/ retry logic |
| Config        | `config.py` | Loads credentials from env vars or `.env` |

## Ground rules for Codex
1. **Never commit secrets** – tokens must stay in env vars.
2. All new functions require **type hints** and **pytest** coverage ≥ 95 %.
3. Use `black`/`ruff` for formatting; run `pre-commit run --all-files`.
4. Tests are executed with `pytest -q`; they must pass in the sandbox.

## Recipes
### Generate typed endpoint stubs
> “Add wrapper functions for the *Vehicles* and *Routes* endpoints based on the
> swagger JSON in `data/samsara-openapi.json`.”

### Bulk‑import telematics CSV
> “Write a CLI command `python -m samsara_fleet.import path/to/*.csv` that
> uploads historical GPS samples to the `/fleet/locations` endpoint.”
