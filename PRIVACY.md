# BusinessBuddy — Privacy Agreement

**Team Jaldhrishti** · Smart India Hackathon 2026 · Problem Statement 26091
**Last updated:** 18 September 2026

This document explains what BusinessBuddy collects, why, who else sees it, and how a user can remove it. It is a fuller version of the notice the bot itself shows on `/privacy` and before first use — the in-app version in `bot/security.py` is the authoritative, user-facing text; this file explains it in more detail for reviewers, judges and contributors.

## 1. Consent first

Nothing described below happens until a user actively taps **I agree** on the privacy notice (shown automatically on first contact, or on demand via `/privacy` or `/security`). Tapping **No thanks**, or never responding, means:

- No message is sent to Groq, Gemini, Sarvam, or any mapping provider.
- Any answers already typed in that session are discarded (`context.user_data.clear()`).
- The bot only ever replies with the privacy notice again until consent is given.

Consent is recorded per user ID (Telegram numeric ID, or WhatsApp phone number) and checked before every conversation turn (`bot/security.py` → `security_gate`).

## 2. What we store, and where

| Data | Where | Protection |
|---|---|---|
| Planning answers (location, margin money, business type, category, income, age, business status) | Our server, SQLite | Encrypted at rest (see §4) |
| Financial plan / loan schedule (amounts, dates, quarters) | Our server, SQLite | Encrypted at rest |
| Progress / outcome records | Our server, SQLite | Encrypted at rest |
| Privacy consent flag (yes/no + timestamp) | Our server, SQLite | Encrypted at rest |
| Chat/phone identifier (Telegram user ID or WhatsApp phone number) | Our server, SQLite | Used as the row key; on WhatsApp this **is** the user's phone number — stated explicitly in the in-app notice |

We do **not** store: passwords, OTPs, PINs, payment credentials, full bank account numbers, or Aadhaar/identity documents — the bot explicitly asks users never to send these, and rejects generic document uploads outright (only a **photo** of a redacted bank letter is accepted, for one narrow OCR feature — see §3).

## 3. Third parties that process data, and why

Only when the corresponding feature is actually used:

| Provider | Receives | Purpose |
|---|---|---|
| **Groq** | Advisory/report-generation inputs (location, business type, financial figures) | Generates the feasibility report and guided-planning follow-ups |
| **Google Gemini** | Translation text; photos of bank sanction letters | Language translation; OCR to extract repayment due dates |
| **Sarvam AI** | Voice note audio | Speech-to-text transcription for voice input |
| **OpenStreetMap (Overpass/Nominatim)**, optionally **Google Places** | Place-name searches, GPS coordinates (only when a user shares location) | Nearby competitor/bank lookup, location resolution |
| **Telegram** or **Meta (WhatsApp Cloud API)** | The message transport itself | Delivering messages — see §5 for the platform-specific caveat |

Each of these providers has its own data-handling policy; BusinessBuddy has no control over their retention once a request is sent. We do not sell data or share it with any party beyond what a used feature requires to function.

## 4. Encryption at rest

The database (`scheduler/secure_database.py`) is never written to disk as a plain SQLite file:

- The whole database is kept in memory (`sqlite3.connect(":memory:")`) during a request, then serialized and encrypted with **Fernet** (symmetric AES-128-CBC + HMAC) before being written to disk, and decrypted back into memory on load.
- The encryption key (`BUSINESSBUDDY_STORAGE_KEY`) lives only in the server's local environment — never in source control, never in chat, never logged (a log-scrubbing filter redacts anything that looks like a key, token, or secret before it reaches any log file).
- Writes are atomic (write to a temp file, then `os.replace`) so a crash mid-write cannot corrupt or partially expose the database.
- A corrupted or tampered file fails closed with an explicit error rather than silently returning wrong data.

## 5. Platform caveat — this is not end-to-end encrypted

Telegram and WhatsApp both operate as an intermediary: the platform provider (Telegram, or Meta for WhatsApp) — and this bot's server — can technically read message content in transit or at their own end, the same as any bot/business account on either platform. This is **not** a peer-to-peer encrypted channel. On WhatsApp specifically, the account identifier is the user's real phone number, not an anonymous ID as on Telegram. Both facts are stated directly in the bot's own `/privacy` notice, not only here.

## 6. User controls

| Command | Effect |
|---|---|
| `/privacy` or `/security` | Re-shows this notice at any time |
| `/deleteplan` | Deletes the user's planning records and consent flag from our database |
| `/stopreminders` | Stops scheduled EMI reminder messages |
| Declining consent | Blocks all external processing for that user from that point on |

**Limits of deletion:** `/deleteplan` removes our own database row. It does **not** retroactively delete:
- Chat history on Telegram/WhatsApp itself (governed by that platform, not us).
- Any copy already sent to a third-party provider (Groq/Gemini/Sarvam/map provider) for a request that already completed — those providers govern their own retention.
- Existing backups, if any are taken of our server.

## 7. Rate limiting and abuse protection

To keep the service available and limit how much data any single actor can push through the system, the bot enforces 12 requests/minute per user and a shared global cap (`bot/security.py` → `RateLimiter`). Requests beyond the limit are silently dropped rather than answered, to avoid producing an outbound flood during abuse. This is a resource-fairness control, not a data-sharing mechanism.

## 8. Accuracy disclaimer

AI-generated content (feasibility reports, translations, OCR-read dates) can be wrong. Users are told directly in the privacy notice to verify amounts and lender terms independently, and that a bank's presence on a map does not prove scheme participation or loan approval. The bot never asks a user to pay for loan approval, and says so explicitly.

## 9. Scope of this document

This describes the BusinessBuddy prototype built for SIH 2026 (PS 26091) as of the date above. It is not a substitute for formal legal review before any production or public deployment; before real users' financial data is processed at scale, this project would need a lawyer-reviewed policy, a named data controller, and compliance with the Indian Digital Personal Data Protection Act (DPDP), 2023.

## 10. Contact

For questions about this policy or a data-deletion request beyond `/deleteplan`, contact the team via the repository listed at the top of the project README.
