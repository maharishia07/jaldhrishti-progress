# Jaldhrishti Progress

Early development checkpoint of Jaldhrishti, a Telegram business-advisory prototype for rural entrepreneurs (Smart India Hackathon, problem statement 26091).

This repository is [jaldhrishti-progress](https://github.com/maharishia07/jaldhrishti-progress). It is separate from the more developed `jaldhrishti-bot` project; features and test results from that project do not describe this checkpoint.

## What this version does

The `/start` conversation asks for a typed location, available margin money and business type. It combines an OpenStreetMap lookup, deterministic financial calculations and a Gemini-generated feasibility summary, then saves a draft repayment schedule in SQLite. Optional document uploads store a Telegram file identifier; this version does not read their contents.

## Quick start

Use Python 3.10 or newer. Run commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS/Linux, activate with `source .venv/bin/activate` and copy with `cp .env.example .env`.

Set `BOT_TOKEN` and `GEMINI_API_KEY` in your local `.env`, then run:

```text
python -m src.main
```

`python main.py` remains a compatibility launcher. Starting either command connects to Telegram and starts the reminder scheduler. Run one instance per bot token. Use synthetic inputs for development and keep credentials out of Git.

## Structure

```text
jaldhrishti-progress/
|-- README.md
|-- PRIVACY.md
|-- .gitignore
|-- .env.example
|-- requirements.txt
|-- main.py                      # Compatibility launcher
|-- src/
|   |-- __init__.py
|   |-- main.py                  # Application startup
|   |-- config/
|   |   `-- settings.py          # Environment and data paths
|   |-- bot/
|   |   `-- handlers.py          # Telegram conversation
|   `-- services/
|       |-- advisory/           # Gemini feasibility report
|       |-- datalayer/          # Nominatim and Overpass clients
|       |-- engine/             # Financial calculations and scheme_rules.json
|       `-- scheduler/          # SQLite persistence and reminders
|-- scripts/                    # Offline demo and opt-in live map check
|-- tests/                      # Offline automated checks
|-- data/
|   |-- input/                  # Local input files
|   `-- output/                 # Ignored runtime data
`-- docs/
    `-- README.md               # Workflow, checks and known limitations
```

The package uses `__init__.py` files for Python imports. API, model and utility folders are not added as empty placeholders; create them when the application needs those responsibilities.

## Configuration and data

- `BOT_TOKEN`: Telegram bot credential.
- `GEMINI_API_KEY`: credential for report generation.
- `JALDHRISHTI_DB`: optional SQLite path override. New installations default to `data/output/jaldhrishti.db`; an existing legacy `scheduler/jaldhrishti.db` is preserved and selected if present.
- Scheme reference rules stay beside the financial engine in `src/services/engine/scheme_rules.json`.

Runtime databases, output files, virtual environments, caches and `.env` are excluded from version control. There is no bundled LGD database in this checkpoint. See [the privacy notice](PRIVACY.md) for actual storage and external processing.

## Checks

```text
python -m unittest discover -s tests -v
```

These checks run offline. The reminder-data demo also runs offline in a temporary database:

```text
python -m scripts.demo_reminder
```

The demo checks storage only; it never sends Telegram messages or touches the user database. The separate map check contacts OpenStreetMap and requires explicit opt-in:

```text
python -m scripts.check_geospatial --live
```

The live map check is not part of routine offline testing.

## Development status

This is an early prototype, not a production-ready financial service. The report is advisory, local map coverage is incomplete, and rule-based loan estimates do not establish lender eligibility or approval. The current conversation requests reports in English; language options in the advisory function are not a complete multilingual user experience.

Security, lender verification and live integration validation remain separate work. Read [the development notes](docs/README.md) before demonstrating or deploying this checkpoint. Contributors can work across modules; the old six-session folder-ownership rule no longer applies.
