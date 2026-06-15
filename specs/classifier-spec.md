# Spec: `classify_safety_tier()`

**File:** `safety.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Determine whether a home repair question is safe to answer directly, requires a cautionary response, or should be refused with a referral to a licensed professional.

---

## Input / Output Contract

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |

**Output:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `"tier"` | `str` | One of: `"safe"`, `"caution"`, `"refuse"` |
| `"reason"` | `str` | One sentence explaining why this tier was assigned |

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Tier definitions

*Write a one-sentence definition for each tier that is precise enough to use as part of your classification prompt. Vague definitions produce inconsistent classifications.*

**safe:**
```
Routine maintenance or low-risk repairs a typical homeowner can complete with basic tools, no permit, and no license, where the worst realistic outcome of a mistake is cosmetic damage or a broken fixture -- never injury, fire, flooding, or structural failure.
```

**caution:**
```
A like-for-like swap or minor repair at an existing location, doable by a motivated homeowner without a permit, that touches a live water or electrical system where a mistake has real cost or mild injury risk -- but the worst realistic outcome is a leak, a tripped breaker, or a damaged fixture.
```

**refuse:**
```
Any repair where an amateur mistake can cause fire, flooding, structural failure, serious injury or death, or that legally requires a licensed professional or permit -- including all gas work, electrical panel/service work, adding new circuits or wiring, removing or modifying walls, and main water line, new plumbing or water heater work.
```

---

### Classification approach

*How will the LLM classify the question? Will you give it just the tier definitions, or also examples (few-shot)? Will you ask it to reason step-by-step before naming the tier, or output the tier directly?*

*Consider: what happens when a question is genuinely ambiguous — e.g., "can I replace my own outlets?" Which tier should that land in, and how does your approach handle questions at the boundary?*

```
Definitions + few-shot boundary examples + a brief reason-before-tier step, with a fail-closed tie-breaker. Definitions alone are too vague at the caution/refuse line and produce inconsistent calls. I include 3-4 few-shot examples chosen specifically to anchor the hardest distinction -- "replace existing" (caution) vs. "add new" (refuse) for electrical -- plus one gas example (always refuse) and one "small fix framing" example. I ask the model to do one short analysis step applying the boundary question before it names a tier, because forcing the reasoning first measurably reduces boundary errors. For genuinely ambiguous questions, the instruction is explicit: classify by what the repair actually requires, not how it's framed, and when uncertain choose the higher-risk tier. Example: "can I replace my own outlets?" is a like-for-like swap on an existing circuit -> caution; but if the question is vague about whether a new outlet/circuit is involved, escalate to refuse.
```

---

### Output format

*How will the LLM communicate the tier and reason back to you? Describe the exact text format you'll ask it to use, so you can parse it reliably.*

*The format you used in Lab 3 (`Label: X / Reasoning: Y`) is a reasonable starting point, but you're not required to use it. Whatever you choose, you'll need to parse it in code — so consider how much variation the LLM might introduce and how you'll handle that.*

```
Three labeled lines, fixed order, one per line:
ANALYSIS: <one or two sentences applying the boundary question>
TIER: <safe|caution|refuse>
REASON: <one sentence?

I parse with a case insensitive regex for TIER:\s*(safe|caution|refuse) and a separate capture for the text after REASON:. The ANALYSIS: line is ignored by the parser -- it exists only to force reasoning before the verdict. I lowercase and strip the captured tier, then validate it against VALID_TIERS. Labeled lines are chosen over raw JSON because the LLM is less likely to wrap them in markdown fences or add stray keys, and a line-based regex tolerates minor formatting drift.
```

---

### Prompt structure

*Write the actual prompt you'll use — both the system message and the user message. Don't describe it — write it. Vague prompt descriptions produce vague prompts, which produce inconsistent classifications.*

**System message:**
```
You are a safety classifier for a home-repair Q&A assistant. Your only job is to assign each question to exactly one safety tier. You do not answer the repair question.

Tiers:
- safe -- Routine, low-risk repairs needing only basic tools, no permit, no license; worst case of a mistake is cosmetic damage or a broken fixture.
- caution -- A like-for-like swap or minor repair at an existing location that touches live water or electrical systems; worst case is a leak, a tripped breaker, or a damaged fixture.
- refuse -- Any repair where a mistake can cause fire, flooding, structural failure, serious injury, or death, or that legally requires a licensed pro or permit. This includes ALL gas work, electrical panel/service work, adding new circuits or wiring, wall removal/modification, main water line work, new plumbing runs, and water heater replacement.

Decision rule for the hardest boundary (caution vs. refuse): ask "if this goes wrong, can it cause fire, flooding, structural failure, injury, or death?" If yes -> refuse. If the worst case is a leak, a tripped breaker, or a broken fixture -> caution.

Critical distinctions:
- Replacing an existing component at the same location (outlet, switch, fixture, faucet) = caution. Adding a new outlet/switch/circuit/wire or running new pipe = refuse.
- Gas -- anything involving gas lines, gas appliances, or a gas smell = refuse, always.
- Walls -- any wall removal/modification = refuse unless the user states a structural engineer already confirmed it is non-load-bearing.
- Water heaters = refuse unless clearly limited to a minor component like an anode rod or heating element.
- Classify by what the repair actually requires, not how the user frames it ("just a small fix," "move it six inches"). When genuinely uncertain, choose the higher-risk tier.

Examples:
Q. "How do I patch a small hole in my drywall?" -> ANALYSIS: cosmetic, basic tools, no system risk. TIER: safe. REASON: Cosmetic repair with no risk of injury, fire or flooding.
Q. "How do I replace an outlet that stopped working?" -> ANALYSIS: like-for-like swap on an existing circuit; worst case is a tripped breaker. TIER: caution. REASON: Swapping an existing component on a live circuit carries mild shock risk but no new wiring.
Q. "How do I add a new outlet in my garage?" -> ANALYSIS: requires a new circuit and wiring from the panel, plus a permit. TIER: refuse. REASON: Adding a circuit creates a latent fire hazard and requires a licensed electrician.
Q. "I just need to extend my gas line a little for a new stove." -> ANALYSIS: any gas work; mistake risks fire, explosion, CO poisoning. TIER: refuse. REASON: All gas line work must be done by a licensed professional.

Output EXACTLY three lines in this format and nothing else:
ANALYSIS: <one or two sentences>
TIER: <safe|caution|refuse>
REASON: <one sentence>
```

**User message:**
```
Classify the home repair question: "{question}"
```

---

### Caution/refuse boundary

*The most consequential classification decision is whether a question lands in "caution" or "refuse." Write down your rule for this boundary — one sentence. Then give two examples of questions that sit close to the line and explain which side they fall on and why.*

```
Rule: If a mistake on this repair can cause fire, flooding, structural failure, serious injury, or death -- or the work requires opening the electrical panel/service, running new wire or pipe, or touching any gas -- it is refuse; if the worst realistic outcome is a tripped breaker, a leak, or a broken fixture from a like-for-like swap at an existing location, it is caution.

Example 1 -- "How do I replace an outlet that stopped working?" -> caution. It's a like-for-like swap on an existing circuit with no new wiring; the worst likely outcome of an error is a tripped breaker, which is recoverable.
Example 2 -- "How do I add a new outlet in my garage?" -> refuse. "Adding" means running a new circuit from the breaker panel through the walls, which requires a permit and creates a latent fire hazard that can go undiscovered for years.
```

---

### Fallback behavior

*What does your function return if the LLM response can't be parsed — e.g., if it produces free-form prose instead of your expected format? What happens when tier validation against `VALID_TIERS` fails?*

*Note: failing open (returning "safe" as a fallback) is more dangerous than failing closed (returning "caution"). Which makes more sense here, and why?*

```
If the response can't be parsed, or the extracted tier isn't in VALID_TIERS, the function should fail closed, not fail open. Returning "safe" is the dangerous failure mode: it would let the responder hand out DIY instructions for a question whose safety the system could not actually verify.

My recommendation: default to "refuse", returning something like {"tier": "refuse", "reason": "Classification failed; defaulting to the safest tier for safety."}

Reasoning:
- The classifier's entire purpose is to gate dangerous output. When the safety signal is unavailable, the system must assume worst-case risk, not best-case.
- "caution" is the textbook "fail closed" answer and is defensible -- but caution still permits the responder to give partial DIY guidance. For a question that was actually refuse-tier, that's exactly the harm the safety layer exists to prevent. "refuse" degrades gracefully: it just refers the user to a professional.
- The cost is asymmetric. A parse error should be rare, so the realistic downside of defaulting to refuse is occasionally over-refusing a genuinely safe question -- annoying but harmless. The downside of defaulting to safe (or even caution) is shipping dangerous instructions. Pay the safe cost.
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 2.*

**One classification that surprised you — question, tier you expected, tier it returned, and why:**

```
Question: "How do I reset a tripped GFCI outlet?"
Expected: caution -- the Tier Guide explicitly lists "Resetting or replacing a GFCI outlet" under the caution tier.
Returned: safe.
Why: The model reasoned that resetting a GFCI is just pressing the button on the outlet, with no system modification and no realistic injury/fire path -- so it landed on safe. This arguably more accurate than the Tier Guide, which lumps "resetting" together with "replacing." Resetting (pressing a button) and replacing (rewiring the device) are genuinely different risk levels, and the classifier split them apart even though my prompt didn't call that distinction out. It's a reminder that the taxonomy's groupings aren't always atomic -- and that a reasoning step can surface a defensible disagreement with the source doc.
```

**One prompt change you made after seeing the first few outputs, and what it fixed:**

```
My first prompt gave definitions only -- no few-shot examples and no rule about user framing. On that version, "I just want to move a light switch six inches" came back as caution: the minimal, casual framing made the model treat it as a small job. But moving a switch means running new wire, which is refuse-tier. I added two things:
1. the explicit rule "Classify by what the repair actually requires, not how the user frames it"
2. the replace-vs-add few-shot examples (replace existing outlet = caution; add new outlet = refuse). After that change, the same question correctly returned refuse. The fix was specifically the anti-framing rule plus the contrastive examples -- definitions alone weren't enough to beat the "it's just a small fix" framing.
```
