# Privacy and data handling: early prototype

Last reviewed: 21 September 2026.

This notice describes the code in `jaldhrishti-progress`. It replaces documentation that described security and messaging features from a different, later version. This checkpoint is intended for development with synthetic data.

## Information handled

The Telegram conversation receives a location, available margin money and proposed business type. Answers are held in process memory while the conversation runs. The application stores the Telegram chat ID, calculated financial-plan JSON, quarterly amounts, due dates and reminder records in SQLite.

For optional document uploads, it stores the Telegram file ID and logs that identifier. It does not download, read or extract the document in this version. Telegram still receives any document sent through the chat. Do not upload identity documents, account details, passwords, PINs or OTPs.

## External processing

- Telegram transports messages and attachments.
- OpenStreetMap Nominatim receives typed location searches.
- OpenStreetMap Overpass receives coordinates and business-tag queries.
- Google Gemini receives location/business information and calculated financial figures to generate the advisory report.

The repository does not integrate WhatsApp, Groq or Sarvam in this checkpoint. Provider retention and account settings are outside this application; do not assume the bot can erase provider copies.

## Storage and controls

SQLite storage is plaintext: this application does not encrypt it. The default path for a new installation is `data/output/jaldhrishti.db`; a legacy database or the `JALDHRISHTI_DB` setting may select another location. Database files and `.env` are ignored by Git, but ignoring a file does not encrypt or protect it from someone with server access.

There is no implemented consent gate, `/privacy`, `/deleteplan`, `/stopreminders` or automated retention policy in this checkpoint. `/cancel` ends the conversation; it does not erase previously stored schedules or Telegram messages. Records require operator-managed removal. Operators must separately manage logs, backups, host access and secrets.

The bot does not enforce private chats or implement the later version's request limiting. Use a private test chat and synthetic inputs until these controls are implemented and reviewed.

## Accuracy and deployment

Generated advice can be wrong. Financial rules are illustrative and map results can be incomplete or contain prototype fallbacks. No result confirms lender participation, eligibility or loan approval. Stored schedule dates are not a verified record of actual borrowing.

Before inviting real users, implement appropriate consent, deletion, retention and access controls, verify service-provider handling, and publish an accurate operational privacy notice with a named contact. This document records current implementation limits; it is not a claim of legal compliance or a security certification.
