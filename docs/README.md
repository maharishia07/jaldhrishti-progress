# Development notes

This documentation describes the early checkpoint in `jaldhrishti-progress`, not the later `jaldhrishti-bot` application.

## Request flow

1. `src.main` loads the root environment, initialises SQLite, registers Telegram handlers and starts the scheduler.
2. `src.bot.handlers` collects location text, available margin money and business type.
3. `src.services.engine.financial_engine` calculates project cost, an illustrative loan and quarterly instalments using its JSON rules.
4. `src.services.datalayer` resolves location through Nominatim and queries Overpass for mapped competitors, using an 8 km default radius.
5. `src.services.advisory.feasibility_engine` asks Gemini for market reach, opportunities, SWOT and suggested pricing.
6. The bot formats the report and stores a schedule through `src.services.scheduler.storage`.

## Module boundaries

Keep conversation formatting in `src/bot`, startup/configuration in `src/main.py` and `src/config`, and reusable calculations or provider integration in the corresponding service package. Add an HTTP API only if one is implemented; Telegram polling does not require a `routes.py` placeholder.

`main.py` at the root delegates to the canonical `python -m src.main` entry point. Imports should use `src.*`, rather than modifying `sys.path` or recreating the old top-level service folders.

## Data handling after the move

New runtime data belongs under ignored `data/output/`. `JALDHRISHTI_DB` can point to a dedicated test database or another persistent path. An existing legacy `scheduler/jaldhrishti.db` remains in place and takes precedence over the new default when no override is supplied; the restructuring does not delete or migrate its records.

`data/input/` is for local inputs and does not imply a supplied dataset. Keep real user information and credentials out of source control. Financial reference rules are versioned with the engine, since they are required application configuration.

## Validation

Run the offline regression checks from the repository root:

```text
python -m unittest discover -s tests -v
```

Validation on 21 September 2026: all **10 offline tests passed**, Python compilation checks passed for `src`, `scripts`, `tests` and `main.py`, and `python -m scripts.demo_reminder` passed using an isolated temporary database without sending messages. `git diff --check` also passed. These checks cover this repository restructuring; they are not a security audit or live-service certification.

External-service availability and real message delivery are not established by offline tests. The original root-level geospatial script is now `scripts/check_geospatial.py`; the reminder demo is `scripts/demo_reminder.py`. Both are safe to import. The map check requires `--live` before external requests. The reminder demo runs offline using a temporary database and checks insert/query/mark behaviour without calling the legacy sender or changing real user records. Run it with `python -m scripts.demo_reminder`.

The advisory module also contains a historical `__main__` demonstration that calls Gemini. Treat `python -m src.services.advisory.feasibility_engine` as a live, potentially chargeable action, not an offline test.

## Known limitations retained from the checkpoint

- Overpass currently substitutes a hard-coded count of four when results are empty or unavailable. This is a placeholder, not measured competition. Its process-local cache has no expiry and queries consider nodes, not complete OSM coverage.
- Unresolved locations can fall through to a lookup at zero coordinates. Provider requests and synchronous work also need review for timeouts and responsiveness.
- The conversation requests English reports even though the advisory function accepts several language codes.
- Scheme reference calculations do not verify actual borrower eligibility, a lender offer or local demand/prices.
- The legacy reminder sender has unresolved amount-formatting and unawaited asynchronous-send defects. Offline storage checks do not verify notification delivery.
- Saved repayment dates derive from report creation, without actual disbursement or explicit schedule confirmation. Do not use them for real repayment obligations.
- This checkpoint lacks the later project's consent gate, private-chat enforcement, request limits, encrypted storage, retention/deletion controls and document OCR. See [PRIVACY.md](../PRIVACY.md).
- Real Telegram, Gemini and map-service smoke tests are separate from offline regression checks. This reorganisation is not evidence of production readiness.

Before public deployment, address these limitations and independently validate finance, privacy, security and real-user flows. Repository cleanup alone does not implement the later application's features.
