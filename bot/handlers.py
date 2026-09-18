"""
bot/handlers.py
===============
Jaldhrishti - Telegram Conversation Flow
-----------------------------------------
This module owns the conversation wiring (ConversationHandler, state
machine, message formatting) AND wires in the real teammate modules:
datalayer (location + competitor density), engine (financial math),
advisory (AI feasibility report), scheduler (loan persistence).

Requires: python-telegram-bot >= 20.0  (async / Application API)
"""

import html
import logging
from datetime import date
from typing import Optional

from telegram import Update, Document
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from datalayer.location_resolver import resolve_location
from datalayer.osm_client import get_business_density
from engine.financial_engine import calculate_financial_plan
from advisory.feasibility_engine import generate_feasibility_report
from scheduler.storage import save_user_loan

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conversation states
# ---------------------------------------------------------------------------
LOCATION, MARGIN_MONEY, BUSINESS_TYPE = range(3)

# Context-data keys (stored per chat in context.user_data)
KEY_LOCATION      = "location_text"
KEY_MARGIN        = "margin_money"
KEY_BUSINESS      = "business_type"
KEY_DOCUMENT_ID   = "uploaded_file_id"   # optional - stored if user sends a doc

_SCHEME_DISPLAY_NAMES = {
    "micro_finance": "Micro Finance Scheme",
    "term_loan": "Term Loan Scheme",
}


# ===========================================================================
# Helpers
# ===========================================================================

def _e(value) -> str:
    """HTML-escape any dynamic text before it goes into a parse_mode=HTML message."""
    return html.escape(str(value)) if value is not None else "N/A"


def _format_report(
    location:       dict,
    density:        dict,
    financial_plan: dict,
    report:         dict,
) -> str:
    """
    Combine the real outputs of all four teammate modules into a single,
    nicely-formatted Telegram HTML message.

    Expected shapes (see the team's build runbook for the full contracts):
      location       - resolve_location() output: village/block/district/state/lat/lon/confidence
      density        - get_business_density() output: competitor_count/sample_places/source
      financial_plan - calculate_financial_plan() output: project_cost/loan_amount/scheme_name/
                       interest_rate_pa/tenure_years/moratorium_months/quarterly_emi/repayment_schedule
      report         - generate_feasibility_report() output: market_reach/opportunity_analysis/
                       swot/pricing_suggestion/full_text
    """
    scheme_display = _SCHEME_DISPLAY_NAMES.get(financial_plan.get("scheme_name"), financial_plan.get("scheme_name"))
    interest_pct = financial_plan.get("interest_rate_pa")
    interest_str = f"{interest_pct * 100:.2f}% p.a." if isinstance(interest_pct, (int, float)) else "N/A"

    schedule = financial_plan.get("repayment_schedule") or []
    first_emi_line = ""
    if schedule:
        first = schedule[0]
        first_emi_line = f"  First instalment  : Quarter {_e(first.get('quarter'))} - ₹{first.get('emi', 0):,.2f}\n"

    density_source_note = (
        "\n  <i>(estimate - limited data for this exact area)</i>" if density.get("source") == "block_fallback" else ""
    )

    swot = report.get("swot") or {}
    swot_lines = "\n".join(
        f"  <b>{label}:</b> {_e(swot.get(key, ''))}"
        for label, key in (
            ("Strengths", "strengths"), ("Weaknesses", "weaknesses"),
            ("Opportunities", "opportunities"), ("Threats", "threats"),
        )
        if swot.get(key)
    ) or "  (not available)"

    doc_line = ""  # appended by caller if a document was uploaded

    divider = "━" * 15

    msg = (
        "\U0001f30a <b>Jaldhrishti - Business Feasibility Report</b>\n"
        f"{divider}\n\n"

        "\U0001f4cd <b>Location</b>\n"
        f"  Village  : {_e(location.get('village'))}\n"
        f"  District : {_e(location.get('district'))}\n"
        f"  State    : {_e(location.get('state'))}\n"
        f"  Match quality : {_e(location.get('confidence'))}\n\n"

        "\U0001f3ea <b>Market Snapshot</b>\n"
        f"  Nearby competitors : {_e(density.get('competitor_count'))} (within 8 km){density_source_note}\n\n"

        "\U0001f4b0 <b>Financial Plan</b>\n"
        f"  Project Cost      : ₹{financial_plan.get('project_cost', 0):,.2f}\n"
        f"  Loan Eligibility  : ₹{financial_plan.get('loan_amount', 0):,.2f}\n"
        f"  Scheme            : {_e(scheme_display)}\n"
        f"  Interest Rate     : {interest_str}\n"
        f"  Tenure            : {_e(financial_plan.get('tenure_years'))} years "
        f"(incl. {_e(financial_plan.get('moratorium_months'))}-month moratorium)\n"
        f"  Quarterly EMI     : ₹{financial_plan.get('quarterly_emi', 0):,.2f}\n"
        f"{first_emi_line}\n"

        "\U0001f4ca <b>Feasibility Snapshot</b>\n"
        f"  <b>Market Reach:</b> {_e(report.get('market_reach') or '(not available)')}\n"
        f"  <b>Opportunity:</b> {_e(report.get('opportunity_analysis') or '(not available)')}\n\n"
        f"{swot_lines}\n\n"
        f"  <b>Suggested Pricing:</b> {_e(report.get('pricing_suggestion') or '(not available)')}\n"

        f"{doc_line}\n"
        f"{divider}\n"
        "\U0001f91d <i>Powered by Jaldhrishti | Built for rural entrepreneurs</i>"
    )
    return msg


def _format_financial_error(error_code: str) -> str:
    """User-facing message for the financial engine's known error cases."""
    messages = {
        "invalid margin money": (
            "⚠️ Please enter a positive margin money amount greater than ₹0."
        ),
        "exceeds scheme limit": (
            "⚠️ With this margin money, your project cost would exceed ₹50,00,000 "
            "- beyond what either concessional scheme covers. Please try a smaller margin amount."
        ),
    }
    return messages.get(
        error_code,
        "⚠️ We couldn't calculate a financial plan for that amount. Please try again with a different figure.",
    )


# ===========================================================================
# Conversation handler callbacks
# ===========================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point - /start command."""
    context.user_data.clear()   # reset any previous session for this user

    await update.message.reply_text(
        "\U0001f30a <b>Namaste! Welcome to Jaldhrishti</b> \U0001f64f\n\n"
        "I help rural entrepreneurs check if a business idea is financially "
        "viable and generate a personalised loan repayment plan - in seconds.\n\n"
        "Let's start! <b>What is your location?</b>\n"
        "<i>(Type your village, block, or district - e.g. Samastipur, Bihar)</i>",
        parse_mode=ParseMode.HTML,
    )
    return LOCATION


async def received_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State: LOCATION - store the location text, ask for margin money."""
    context.user_data[KEY_LOCATION] = update.message.text.strip()

    await update.message.reply_text(
        "✅ Got it!\n\n"
        "\U0001f4b0 <b>How much margin money do you have available?</b>\n"
        "<i>(Enter amount in ₹ - e.g. 100000)</i>",
        parse_mode=ParseMode.HTML,
    )
    return MARGIN_MONEY


async def received_margin_money(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State: MARGIN_MONEY - validate & store, ask for business type."""
    raw = update.message.text.strip().replace(",", "").replace("₹", "")

    try:
        margin = float(raw)
        if margin <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter a valid positive number for the amount.\n"
            "<i>Example: 100000 or 1,00,000</i>",
            parse_mode=ParseMode.HTML,
        )
        return MARGIN_MONEY   # stay in the same state

    context.user_data[KEY_MARGIN] = margin

    await update.message.reply_text(
        "✅ Noted!\n\n"
        "\U0001f3ea <b>What type of business are you planning?</b>\n"
        "<i>(E.g. Kirana store, Tailoring, Dairy farming, Mobile repair shop...)</i>",
        parse_mode=ParseMode.HTML,
    )
    return BUSINESS_TYPE


async def received_business_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State: BUSINESS_TYPE - collect last answer, run all real modules, send report."""
    context.user_data[KEY_BUSINESS] = update.message.text.strip()

    await update.message.reply_text(
        "⏳ Analysing your inputs... please wait a moment.",
        parse_mode=ParseMode.HTML,
    )

    location_text = context.user_data[KEY_LOCATION]
    margin_money  = context.user_data[KEY_MARGIN]
    business_type = context.user_data[KEY_BUSINESS]

    # ------------------------------------------------------------------ #
    # Financial plan FIRST - if this fails validation, tell the user      #
    # clearly instead of running the rest of the pipeline on bad numbers. #
    # ------------------------------------------------------------------ #
    try:
        financial_plan = calculate_financial_plan(margin_money)
    except Exception as exc:
        logger.error("calculate_financial_plan crashed: %s", exc)
        await update.message.reply_text(
            "⚠️ Something went wrong calculating your financial plan. Please try /start again.",
        )
        return ConversationHandler.END

    if "error" in financial_plan:
        await update.message.reply_text(
            _format_financial_error(financial_plan["error"]),
            parse_mode=ParseMode.HTML,
        )
        return ConversationHandler.END

    # ------------------------------------------------------------------ #
    # Remaining calls wrapped individually so one failure never crashes   #
    # the whole response - each falls back to a safe placeholder shape.   #
    # ------------------------------------------------------------------ #
    try:
        location = resolve_location(location_text)
    except Exception as exc:
        logger.error("resolve_location failed: %s", exc)
        location = {"village": "Unknown", "district": "Unknown", "state": "Unknown",
                    "lat": None, "lon": None, "confidence": "low"}

    try:
        density = get_business_density(location.get("lat") or 0.0, location.get("lon") or 0.0, business_type)
    except Exception as exc:
        logger.error("get_business_density failed: %s", exc)
        density = {"competitor_count": "N/A", "sample_places": [], "source": "unavailable"}

    try:
        report = generate_feasibility_report(location, business_type, financial_plan, language="en")
    except Exception as exc:
        logger.error("generate_feasibility_report failed: %s", exc)
        report = {"market_reach": "", "opportunity_analysis": "", "pricing_suggestion": "",
                  "swot": {}, "full_text": "Feasibility report unavailable right now."}

    # ------------------------------------------------------------------ #
    # Format & send combined reply                                         #
    # ------------------------------------------------------------------ #
    formatted = _format_report(location, density, financial_plan, report)
    await update.message.reply_text(formatted, parse_mode=ParseMode.HTML)

    # ------------------------------------------------------------------ #
    # Persist the loan so Role 5's reminder scheduler can find it later.  #
    # Fire-and-forget; failure must not break the flow the user just saw. #
    # ------------------------------------------------------------------ #
    try:
        save_user_loan(update.effective_chat.id, financial_plan, date.today().isoformat())
    except Exception as exc:
        logger.error("save_user_loan failed: %s", exc)

    return ConversationHandler.END


async def received_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles optional document uploads at ANY point during the conversation.
    Stores the file_id and acknowledges receipt - does NOT parse the file.

    Returns the current conversation state so the ConversationHandler keeps
    the user exactly where they were before the upload.
    """
    doc: Document = update.message.document
    context.user_data[KEY_DOCUMENT_ID] = doc.file_id
    logger.info("Document received - file_id: %s", doc.file_id)

    try:
        from scheduler.storage import save_uploaded_document
        save_uploaded_document(update.effective_chat.id, doc.file_id)
    except Exception as exc:
        logger.error("save_uploaded_document failed: %s", exc)

    await update.message.reply_text(
        "\U0001f4ce <b>Received!</b> Your document has been saved.",
        parse_mode=ParseMode.HTML,
    )

    if KEY_BUSINESS in context.user_data:
        return BUSINESS_TYPE
    if KEY_MARGIN in context.user_data:
        return BUSINESS_TYPE
    if KEY_LOCATION in context.user_data:
        return MARGIN_MONEY
    return LOCATION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allow the user to abort the conversation at any time with /cancel."""
    context.user_data.clear()
    await update.message.reply_text(
        "\U0001f6d1 Session cancelled. Send /start whenever you are ready to try again.",
    )
    return ConversationHandler.END


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for unexpected input outside an active conversation."""
    await update.message.reply_text(
        "\U0001f44b Send /start to begin your business feasibility analysis.",
    )


# ===========================================================================
# Factory - called from main.py to attach all handlers to the Application
# ===========================================================================

def register_handlers(app: Application) -> None:
    """
    Wire every handler into the Application instance.
    Call this once from main.py after creating the Application.
    """
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_location),
                MessageHandler(filters.Document.ALL, received_document),
            ],
            MARGIN_MONEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_margin_money),
                MessageHandler(filters.Document.ALL, received_document),
            ],
            BUSINESS_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_business_type),
                MessageHandler(filters.Document.ALL, received_document),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        name="jaldhrishti_conv",
        persistent=False,
    )

    app.add_handler(conv_handler)

    # Catch messages outside an active conversation
    app.add_handler(MessageHandler(filters.ALL, fallback))
