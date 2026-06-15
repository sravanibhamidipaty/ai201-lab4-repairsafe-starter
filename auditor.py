import json
import os
from collections import Counter
from datetime import datetime, timezone

from config import LOG_FILE, LLM_MODEL

QUESTION_LIMIT = 300
RESPONSE_PREVIEW_LIMIT = 200
_CONSOLE_QUESTION_LIMIT = 60

# Aggregated metrics: every SUMMARY_INTERVAL interactions, append a rollup record
# to SESSION_SUMMARY_FILE alongside the per-interaction audit log.
SESSION_SUMMARY_FILE = os.path.join(os.path.dirname(LOG_FILE) or ".", "session_summary.jsonl")
SUMMARY_INTERVAL = 5


def log_interaction(question: str, tier: str, response: str) -> None:
    """
    Append a structured record of this interaction to the audit log (JSONL).

    Writes one JSON object per line to LOG_FILE so the file stays append-only and
    independently parseable line by line. Truncates the question to 300 chars and
    the response preview to 200 chars, creates the logs/ directory if missing, and
    prints a one-line summary to the terminal.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tier": tier,
        "question": question[:QUESTION_LIMIT],
        "response_preview": response[:RESPONSE_PREVIEW_LIMIT],
        "model": LLM_MODEL,
        "response_length": len(response),
    }

    # Ensure logs/ exists — .gitkeep only covers fresh checkouts, not deployments.
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # One record, one line — json.dumps (not json.dump with indent) keeps JSONL valid.
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    console_question = question[:_CONSOLE_QUESTION_LIMIT]
    if len(question) > _CONSOLE_QUESTION_LIMIT:
        console_question += "…"
    print(f'[LOGGED] tier={tier} | "{console_question}" → {len(response)} chars')

    _maybe_write_session_summary()


def _read_audit_records() -> list:
    """Read and parse every record in the audit log, skipping any corrupt line."""
    if not os.path.exists(LOG_FILE):
        return []
    records = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # one bad line never breaks the rest of the file
    return records


def _maybe_write_session_summary() -> None:
    """Every SUMMARY_INTERVAL interactions, append an aggregated summary record.

    Recomputed from the audit log itself (stateless) so it stays correct even
    across restarts. Records total interactions, the tier distribution, and the
    3 most recent questions.
    """
    records = _read_audit_records()
    total = len(records)
    if total == 0 or total % SUMMARY_INTERVAL != 0:
        return

    tier_distribution = dict(Counter(r.get("tier", "unknown") for r in records))
    recent_questions = [r.get("question", "") for r in records[-3:]]

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total_interactions": total,
        "tier_distribution": tier_distribution,
        "recent_questions": recent_questions,
    }

    with open(SESSION_SUMMARY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    print(
        f"[SUMMARY] {total} interactions logged | "
        f"tiers={tier_distribution} → {SESSION_SUMMARY_FILE}"
    )
