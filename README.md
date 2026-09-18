# Jaldhrishti

AI-driven hyper-local business advisory and financial structuring assistant for rural micro-entrepreneurs, delivered as a Telegram bot. Built for Smart India Hackathon — Problem Statement 26091.

## Folder structure

| Folder | Owns | Role |
|---|---|---|
| `bot/` | Conversation flow (`handlers.py`) + final wiring (`main.py`) | Role 1 + Role 6 |
| `engine/` | Deterministic financial calculations (`financial_engine.py`, `scheme_rules.json`) | Role 2 |
| `advisory/` | Gemini-based feasibility report (`feasibility_engine.py`) | Role 3 |
| `datalayer/` | Location resolution + competitor density (`location_resolver.py`, `osm_client.py`) | Role 4 |
| `scheduler/` | SQLite storage + EMI reminders (`storage.py`, `reminders.py`) | Role 5 |

Full role requirements, function contracts, and paste-ready Antigravity prompts: see the team's Build Runbook.

## Rule

Only write files inside your own assigned folder. This is what lets six independent Antigravity sessions merge without conflicts.

## Setup (once your module needs it)

1. Copy `.env.example` to `.env` and fill in `BOT_TOKEN` (from Telegram's @BotFather) and `GEMINI_API_KEY` (free at aistudio.google.com).
2. `pip install -r requirements.txt`
3. Add whatever libraries your module needs to `requirements.txt`.
