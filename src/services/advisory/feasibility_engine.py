"""
feasibility_engine.py
=====================
Jaldhrishti – Rural Business Feasibility Bot  |  Module: AI Report Generator
-----------------------------------------------------------------------------
Generates AI-powered feasibility reports for rural Indian micro-businesses
using Google's Gemini API (google-genai SDK ≥ 1.0).

This module is intentionally STAND-ALONE — it does NOT depend on any other
Jaldhrishti module (no bot, no financial-math layer, no location service).

Quick start
-----------
    export GEMINI_API_KEY="your-key-from-aistudio.google.com"
    python feasibility_engine.py          # runs 3 built-in test cases

Public API
----------
    from feasibility_engine import generate_feasibility_report

    report = generate_feasibility_report(
        location={
            "village": "Rajpur", "block": "Hajipur",
            "district": "Vaishali", "state": "Bihar",
            "confidence": "high",               # or "low"
            "competitor_count": 4,              # optional
        },
        business_type="Retail Kirana Store",
        financial_plan={
            "project_cost": 150000,
            "loan_amount":  100000,
            "scheme_name":  "PM SVANidhi",
        },
        language="hi",                          # ISO 639-1; see _LANG_META
    )
    # report keys: market_reach, opportunity_analysis, swot, pricing_suggestion, full_text

Environment variables
---------------------
    GEMINI_API_KEY   – Google AI Studio free-tier key (never hard-coded here)
"""

from __future__ import annotations

import logging
import os
import re
import textwrap
import time
from typing import Any

from google import genai
from google.genai import types as genai_types

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language meta-table  (ISO 639-1 → display name + native instruction)
# ---------------------------------------------------------------------------
_LANG_META: dict[str, dict[str, str]] = {
    "en": {
        "name": "English",
        "instruction": (
            "Respond entirely in clear, simple English suitable for "
            "a semi-literate rural reader."
        ),
    },
    "hi": {
        "name": "Hindi",
        "instruction": (
            "पूरी रिपोर्ट सरल हिंदी में लिखें जो एक अर्ध-साक्षर "
            "ग्रामीण पाठक के लिए उपयुक्त हो।"
        ),
    },
    "ta": {
        "name": "Tamil",
        "instruction": (
            "முழு அறிக்கையையும் எளிய தமிழில் எழுதவும், "
            "கிராமப்புற வாசகர்களுக்கு ஏற்றதாக இருக்க வேண்டும்."
        ),
    },
    "te": {
        "name": "Telugu",
        "instruction": (
            "మొత్తం నివేదికను సరళమైన తెలుగులో రాయండి, "
            "గ్రామీణ పాఠకులకు అనుకూలంగా ఉండాలి."
        ),
    },
    "mr": {
        "name": "Marathi",
        "instruction": (
            "संपूर्ण अहवाल सोप्या मराठीत लिहा, "
            "जो अर्ध-साक्षर ग्रामीण वाचकांसाठी योग्य असेल."
        ),
    },
    "bn": {
        "name": "Bengali",
        "instruction": (
            "সম্পূর্ণ প্রতিবেদনটি সহজ বাংলায় লিখুন, "
            "যা আধা-সাক্ষর গ্রামীণ পাঠকদের জন্য উপযুক্ত।"
        ),
    },
    "kn": {
        "name": "Kannada",
        "instruction": (
            "ಸಂಪೂರ್ಣ ವರದಿಯನ್ನು ಸರಳ ಕನ್ನಡದಲ್ಲಿ ಬರೆಯಿರಿ, "
            "ಗ್ರಾಮೀಣ ಓದುಗರಿಗೆ ಸೂಕ್ತವಾಗಿ."
        ),
    },
}

_DEFAULT_LANG_INSTRUCTION = (
    "Respond entirely in clear, simple English suitable for a semi-literate rural reader."
)

# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------
ReportDict = dict[str, Any]

_EMPTY_SWOT: dict[str, str] = {
    "strengths": "",
    "weaknesses": "",
    "opportunities": "",
    "threats": "",
}

_EMPTY_REPORT: ReportDict = {
    "market_reach": "",
    "opportunity_analysis": "",
    "swot": _EMPTY_SWOT,
    "pricing_suggestion": "",
    "full_text": "",
}


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _fmt_inr(val: Any) -> str:
    """Format a numeric value as an INR string; pass non-numeric through."""
    if isinstance(val, (int, float)):
        return f"₹{val:,.0f}"
    return str(val)


def _build_prompt(
    location: dict,
    business_type: str,
    financial_plan: dict,
    language: str,
) -> str:
    """Return the fully-assembled Gemini prompt string."""

    lang_code = language.lower()
    lang_meta = _LANG_META.get(lang_code, {})
    lang_name = lang_meta.get("name", language)
    lang_instruction = lang_meta.get("instruction", _DEFAULT_LANG_INSTRUCTION)

    # — Location block —
    village = location.get("village", "N/A")
    block = location.get("block", "N/A")
    district = location.get("district", "N/A")
    state = location.get("state", "N/A")
    confidence = location.get("confidence", "N/A")
    competitor_count = location.get("competitor_count")

    loc_lines = [
        f"Village          : {village}",
        f"Block            : {block}",
        f"District         : {district}",
        f"State            : {state}",
        f"Location quality : {confidence}",
    ]
    if competitor_count is not None:
        loc_lines.append(f"Known competitors: {competitor_count}")
    location_block = "\n".join(loc_lines)

    # — Financial block —
    project_cost = _fmt_inr(financial_plan.get("project_cost", "N/A"))
    loan_amount = _fmt_inr(financial_plan.get("loan_amount", "N/A"))
    scheme_name = financial_plan.get("scheme_name", "N/A")

    financial_block = (
        f"Total project cost  : {project_cost}\n"
        f"Loan amount requested: {loan_amount}\n"
        f"Government scheme   : {scheme_name}"
    )

    # — Full prompt —
    prompt = textwrap.dedent(f"""
        You are a practical rural business advisor helping Indian micro-entrepreneurs.
        {lang_instruction}

        ════════════════════════════════════════════════════
        STRICT FINANCIAL RULE — READ BEFORE WRITING ANYTHING
        ════════════════════════════════════════════════════
        The rupee figures below are FIXED facts supplied by the applicant.
        You MUST use ONLY the numbers given in the FINANCIAL PLAN section.
        Never invent, estimate, round, or change any rupee figure.
        If you need to reference money, copy the exact value provided.

        ════════════════════════════════════════════════════
        BUSINESS FACTS  (do NOT alter or contradict these)
        ════════════════════════════════════════════════════
        Business type : {business_type}

        LOCATION
        --------
        {location_block}

        FINANCIAL PLAN
        --------------
        {financial_block}

        ════════════════════════════════════════════════════
        YOUR TASK — output EXACTLY these four sections, nothing else.
        Use these headers verbatim; they are needed for automated parsing.
        ════════════════════════════════════════════════════

        ## MARKET REACH
        2–3 sentences: who will buy from this business and how far they will
        travel, given the location above.  Be specific to {district}, {state}.

        ## OPPORTUNITY ANALYSIS
        Exactly ONE paragraph (3–4 sentences) describing a specific under-served
        gap in this business category that the entrepreneur should target.

        ## SWOT ANALYSIS
        Four lines, one per item, in this exact format:
        **Strengths:** <one concise sentence>
        **Weaknesses:** <one concise sentence>
        **Opportunities:** <one concise sentence>
        **Threats:** <one concise sentence>

        ## PRICING SUGGESTION
        2–3 sentences suggesting a realistic price range for this business's
        main products or services, suited to purchasing power in {district}, {state}.

        Output language: {lang_name}.  Keep every section brief and practical.
        CRITICAL: Always write the four section headers (## MARKET REACH,
        ## OPPORTUNITY ANALYSIS, ## SWOT ANALYSIS, ## PRICING SUGGESTION)
        in English exactly as shown above, even when all other content is
        written in {lang_name}.  This is required for automated parsing.
    """).strip()

    return prompt


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _extract_section(text: str, header: str) -> str:
    """
    Return the content block that follows `## <header>` up to the next
    `##` section or end-of-string.  Returns "" if the header is not found.
    """
    pattern = rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_swot(swot_block: str) -> dict[str, str]:
    """
    Extract the four SWOT components from the SWOT section text.
    Each key defaults to "" if its line is not found.
    """
    patterns = {
        "strengths":    r"\*{0,2}Strengths?\*{0,2}[:\-]?\s*(.+)",
        "weaknesses":   r"\*{0,2}Weaknesses?\*{0,2}[:\-]?\s*(.+)",
        "opportunities":r"\*{0,2}Opportunities?\*{0,2}[:\-]?\s*(.+)",
        "threats":      r"\*{0,2}Threats?\*{0,2}[:\-]?\s*(.+)",
    }
    # The prompt asks for "**Strengths:** text" — the closing ** falls right
    # after the colon, which the patterns above don't consume, so it leaks
    # into the captured group as a stray prefix. Strip it off here instead
    # of trying to make the regex handle every asterisk placement the model
    # might produce.
    result = {}
    for key, pat in patterns.items():
        m = re.search(pat, swot_block, re.IGNORECASE)
        result[key] = m.group(1).strip().lstrip("*").strip() if m else ""
    return result


def _parse_response(raw_text: str) -> ReportDict:
    """
    Parse Gemini's raw output into the structured ReportDict.

    Graceful fallback: any section that cannot be found is left as "".
    `full_text` always contains the complete raw response so the caller
    is never left with nothing useful.
    """
    report: ReportDict = {
        "market_reach":       _extract_section(raw_text, "MARKET REACH"),
        "opportunity_analysis": _extract_section(raw_text, "OPPORTUNITY ANALYSIS"),
        "swot":               _parse_swot(_extract_section(raw_text, "SWOT ANALYSIS")),
        "pricing_suggestion": _extract_section(raw_text, "PRICING SUGGESTION"),
        "full_text":          raw_text,
    }
    return report


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_feasibility_report(
    location: dict,
    business_type: str,
    financial_plan: dict,
    language: str = "en",
) -> ReportDict:
    """
    Generate an AI-powered feasibility report for a rural Indian micro-business.

    Parameters
    ----------
    location : dict
        Required keys : village, block, district, state, confidence ("high"|"low")
        Optional keys : competitor_count (int)

    business_type : str
        Human-readable business name, e.g. "Dairy farming", "Tailoring shop"

    financial_plan : dict
        Required keys : project_cost (int|float), loan_amount (int|float),
                        scheme_name (str)

    language : str
        ISO 639-1 code.  Supported: en, hi, ta, te, mr, bn, kn.
        Falls back to English instructions for unsupported codes.

    Returns
    -------
    dict with keys:
        market_reach         : str
        opportunity_analysis : str
        swot                 : dict  (strengths / weaknesses /
                                      opportunities / threats)
        pricing_suggestion   : str
        full_text            : str   ← always populated; complete raw response

    Raises
    ------
    EnvironmentError
        If GEMINI_API_KEY is not set in the environment.
    google.genai.errors.APIError
        On Gemini API errors (network, quota, invalid key, etc.).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set.\n"
            "Get a free key at https://aistudio.google.com/app/apikey "
            "and set it with:  export GEMINI_API_KEY=your_key"
        )

    client = genai.Client(api_key=api_key)

    prompt = _build_prompt(location, business_type, financial_plan, language)
    logger.debug("Prompt length: %d chars", len(prompt))

    t0 = time.perf_counter()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            max_output_tokens=3000,
        ),
    )

    elapsed = time.perf_counter() - t0
    logger.debug("Gemini responded in %.2f s", elapsed)

    raw_text = (response.text or "").strip()

    if not raw_text:
        logger.warning("Gemini returned an empty response for business_type=%r", business_type)
        return {
            **_EMPTY_REPORT,
            "swot": dict(_EMPTY_SWOT),
            "full_text": "[No response received from Gemini]",
        }

    return _parse_response(raw_text)


# ---------------------------------------------------------------------------
# Built-in test / demo  (python feasibility_engine.py)
# ---------------------------------------------------------------------------

_TEST_CASES: list[dict] = [
    {
        "label": "🐄  Dairy farming – Tamil Nadu (English)",
        "location": {
            "village": "Therkku Vallam",
            "block": "Kumbakonam",
            "district": "Thanjavur",
            "state": "Tamil Nadu",
            "confidence": "high",
            "competitor_count": 3,
        },
        "business_type": "Dairy farming and milk supply",
        "financial_plan": {
            "project_cost": 250000,
            "loan_amount": 175000,
            "scheme_name": "Pashu Kisan Credit Card",
        },
        "language": "en",
    },
    {
        "label": "✂️  Tailoring shop – Uttar Pradesh (Hindi)",
        "location": {
            "village": "Rampur Kalan",
            "block": "Phulpur",
            "district": "Prayagraj",
            "state": "Uttar Pradesh",
            "confidence": "high",
            "competitor_count": 2,
        },
        "business_type": "Tailoring and garment stitching",
        "financial_plan": {
            "project_cost": 80000,
            "loan_amount": 50000,
            "scheme_name": "PM Vishwakarma Yojana",
        },
        "language": "hi",
    },
    {
        "label": "🛒  Retail kirana store – Bihar (English, low-confidence location)",
        "location": {
            "village": "Mahnar Bazar",
            "block": "Mahnar",
            "district": "Vaishali",
            "state": "Bihar",
            "confidence": "low",
            # no competitor_count → tests optional field
        },
        "business_type": "Retail kirana (grocery) store",
        "financial_plan": {
            "project_cost": 150000,
            "loan_amount": 100000,
            "scheme_name": "PM SVANidhi",
        },
        "language": "hi",
    },
]


def _run_tests() -> None:
    """Pretty-print results for all built-in test cases."""

    total = len(_TEST_CASES)
    passed = 0

    print("\n" + "═" * 72)
    print("  Jaldhrishti — Feasibility Engine  |  Test Suite")
    print("═" * 72)

    for idx, case in enumerate(_TEST_CASES, 1):
        print(f"\n[{idx}/{total}]  {case['label']}")
        print("─" * 72)

        try:
            t0 = time.perf_counter()
            report = generate_feasibility_report(
                location=case["location"],
                business_type=case["business_type"],
                financial_plan=case["financial_plan"],
                language=case["language"],
            )
            elapsed = time.perf_counter() - t0

            print(f"⏱  API call time : {elapsed:.2f}s")
            print(f"\n📍 MARKET REACH\n{report['market_reach'] or '(empty)'}")
            print(f"\n💡 OPPORTUNITY\n{report['opportunity_analysis'] or '(empty)'}")

            swot = report["swot"]
            print(
                f"\n📊 SWOT\n"
                f"  Strengths    : {swot.get('strengths',     '') or '(empty)'}\n"
                f"  Weaknesses   : {swot.get('weaknesses',    '') or '(empty)'}\n"
                f"  Opportunities: {swot.get('opportunities', '') or '(empty)'}\n"
                f"  Threats      : {swot.get('threats',       '') or '(empty)'}"
            )
            print(f"\n💰 PRICING SUGGESTION\n{report['pricing_suggestion'] or '(empty)'}")

            # ── Assertions ────────────────────────────────────────────────
            fails: list[str] = []
            if not report["full_text"]:
                fails.append("full_text is empty")
            if not report["market_reach"]:
                fails.append("market_reach section could not be parsed (header mismatch?)")

            # Timing — informational only; free-tier latency is not a code bug
            if elapsed > 20:
                print(f"   ⚡ Note: API call took {elapsed:.1f}s (free-tier latency; "
                      f"paid quota typically < 5s)")

            # Verify rupee figures are not CONTRADICTED (not merely absent).
            # The model legitimately omits project_cost/loan_amount in narrative
            # text; only flag if it states a wrong figure in context.
            fp = case["financial_plan"]
            full_norm = report["full_text"].replace(",", "").replace(" ", "")
            kw_patterns = {
                "project_cost": r"(?:project.cost|total.cost)[^₹₨]{0,40}[₹₨]\s*([\d]+)",
                "loan_amount":  r"(?:loan.amount|loan)[^₹₨]{0,40}[₹₨]\s*([\d]+)",
            }
            for key, pattern in kw_patterns.items():
                val = fp.get(key)
                if not isinstance(val, (int, float)):
                    continue
                expected = int(val)
                for m in re.finditer(pattern, full_norm, re.IGNORECASE):
                    found = int(m.group(1))
                    if found != expected:
                        fails.append(
                            f"Contradicted {key}: model said ₹{found:,} "
                            f"but given value is ₹{expected:,}"
                        )

            if fails:
                for f in fails:
                    print(f"⚠  WARNING: {f}")
            else:
                print("\n✅  PASS")
                passed += 1

        except EnvironmentError as exc:
            print(f"❌  SKIPPED — {exc}")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"❌  FAIL — {type(exc).__name__}: {exc}")

    print("\n" + "═" * 72)
    print(f"  Result: {passed}/{total} tests passed")
    print("═" * 72 + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    _run_tests()
