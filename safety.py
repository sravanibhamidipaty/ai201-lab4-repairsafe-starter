import re

from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, VALID_TIERS

_client = Groq(api_key=GROQ_API_KEY)

# Fail-closed default. If the response can't be parsed or the tier isn't
# recognized, we never return "safe" — that would let the responder hand out
# DIY instructions for a question whose safety we couldn't verify. "refuse" is
# the most protective tier. (The starter TODO suggested "caution"; either is a
# valid fail-closed choice — change this one constant to switch.)
FALLBACK_TIER = "refuse"

SYSTEM_PROMPT = """You are a safety classifier for a home-repair Q&A assistant. Your only job is to assign each question to exactly one safety tier. You do not answer the repair question.

Tiers:
- safe — Routine, low-risk repairs needing only basic tools, no permit, no license; worst case of a mistake is cosmetic damage or a broken fixture.
- caution — A like-for-like swap or minor repair at an existing location that touches live water or electrical systems; worst case is a leak, a tripped breaker, or a damaged fixture.
- refuse — Any repair where a mistake can cause fire, flooding, structural failure, serious injury, or death, or that legally requires a licensed pro or permit. This includes ALL gas work, electrical panel/service work, adding new circuits or wiring, wall removal/modification, main water line work, new plumbing runs, and water heater replacement.
- legal — Questions that are not primarily about the physical danger of doing a repair, but about its legal, permitting, code-compliance, liability, or responsibility dimension — e.g., whether a permit is required, who pays for or is responsible for a repair, what local code allows, or landlord/tenant obligations.

Decision rule for the hardest boundary (caution vs. refuse): ask "if this goes wrong, can it cause fire, flooding, structural failure, injury, or death?" If yes -> refuse. If the worst case is a leak, a tripped breaker, or a broken fixture -> caution.

Decision rule for legal vs. the others: ask what the user is actually asking for. If they want to know HOW to physically do the work, classify by physical risk (safe/caution/refuse) even if a permit is mentioned. If they are asking WHETHER a permit/inspection is needed, WHO is responsible or must pay, what the CODE or LAW allows, or about landlord/tenant rights, classify it legal.

Critical distinctions:
- Replacing an existing component at the same location (outlet, switch, fixture, faucet) = caution. Adding a new outlet/switch/circuit/wire or running new pipe = refuse.
- Gas — anything involving gas lines, gas appliances, or a gas smell = refuse, always.
- Walls — any wall removal/modification = refuse unless the user states a structural engineer already confirmed it is non-load-bearing.
- Water heaters = refuse unless clearly limited to a minor component like an anode rod or heating element.
- Classify by what the repair actually requires, not how the user frames it ("just a small fix," "move it six inches"). When genuinely uncertain, choose the higher-risk tier.

Examples:
Q: "How do I patch a small hole in my drywall?" -> ANALYSIS: cosmetic, basic tools, no system risk. TIER: safe. REASON: Cosmetic repair with no risk of injury, fire, or flooding.
Q: "How do I replace an outlet that stopped working?" -> ANALYSIS: like-for-like swap on an existing circuit; worst case is a tripped breaker. TIER: caution. REASON: Swapping an existing component on a live circuit carries mild shock risk but no new wiring.
Q: "How do I add a new outlet in my garage?" -> ANALYSIS: requires a new circuit and wiring from the panel, plus a permit. TIER: refuse. REASON: Adding a circuit creates a latent fire hazard and requires a licensed electrician.
Q: "I just need to extend my gas line a little for a new stove." -> ANALYSIS: any gas work; mistake risks fire, explosion, CO poisoning. TIER: refuse. REASON: All gas line work must be done by a licensed professional.
Q: "Do I need a permit to build a deck in my backyard?" -> ANALYSIS: asks about permitting requirements, not how to build; this is a legal/code question. TIER: legal. REASON: The question is about permit requirements rather than the physical work.
Q: "Can my landlord make me pay for a plumbing repair?" -> ANALYSIS: asks about responsibility/liability between landlord and tenant, not a repair procedure. TIER: legal. REASON: This is a landlord/tenant liability question, not a repair task.

Output EXACTLY three lines in this format and nothing else:
ANALYSIS: <one or two sentences>
TIER: <safe|caution|refuse|legal>
REASON: <one sentence>"""


def _parse_tier(text: str) -> str | None:
    """Extract the tier token after 'TIER:', normalize it, and validate it.

    Returns a tier guaranteed to be in VALID_TIERS, or None if no valid tier
    can be recovered. Tolerates capitalization ("Refuse"), wrapping quotes
    ("'refuse'"), markdown emphasis (**refuse**), and trailing punctuation.
    """
    match = re.search(r"TIER\s*:\s*[\*\"'`]*\s*([A-Za-z]+)", text, re.IGNORECASE)
    if not match:
        return None
    tier = match.group(1).strip().strip("\"'`*.").lower()
    return tier if tier in VALID_TIERS else None


def _parse_reason(text: str) -> str | None:
    """Extract the one-sentence reason after 'REASON:', stripped of wrappers."""
    match = re.search(r"REASON\s*:\s*(.+)", text, re.IGNORECASE)
    if not match:
        return None
    reason = match.group(1).strip().strip("\"'`*")
    return reason or None


def classify_safety_tier(question: str) -> dict:
    """
    Classify a home repair question into one of three safety tiers.

    Sends a single LLM chat completion (no tools, no history) asking the model
    to reason briefly, then emit ANALYSIS/TIER/REASON lines. The tier is parsed,
    normalized, and validated against VALID_TIERS before being returned.

    Returns a dict with:
      - "tier"   : str — one of "safe", "caution", "refuse"
      - "reason" : str — a brief explanation of why this tier was assigned

    Fails closed: on any error, unparseable output, or unrecognized tier, returns
    FALLBACK_TIER rather than guessing "safe".
    """
    try:
        response = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f'Classify this home repair question:\n\n"{question}"',
                },
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
    except Exception as exc:
        return {
            "tier": FALLBACK_TIER,
            "reason": f"Classification request failed ({exc}); defaulting to the safest tier.",
        }

    tier = _parse_tier(raw)
    if tier is None:
        return {
            "tier": FALLBACK_TIER,
            "reason": "Could not parse a valid tier from the model response; defaulting to the safest tier.",
        }

    reason = _parse_reason(raw) or "No reason provided by the classifier."
    return {"tier": tier, "reason": reason}
