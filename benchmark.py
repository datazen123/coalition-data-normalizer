"""
Real-data benchmark: measures this repo's cross-system reconciliation
approach against the Febrl 4 record-linkage benchmark (Christen, ANU),
loaded via the actively-maintained `recordlinkage` Python package. Febrl 4
is a structural gift for this repo specifically: it's already split into
two separate 5,000-record tables (dataset4a / dataset4b) with a known 1:1
true-match ground truth - i.e. already shaped like "two partners, no shared
key" before we touch it.

This is a SEPARATE scenario from normalize.py's equipment-status demo above
- Febrl is person-identity data (name/address/date-of-birth), not equipment
records, so it proves the same reconciliation architecture generalizes to a
second, real domain (a personnel/roster reconciliation problem - a genuine
coalition-interoperability need in its own right) rather than replacing or
reframing the equipment-status story.

Design: 30 records are true cross-partner matches (present in both tables,
under fresh, partner-specific IDs and formatting conventions with no shared
key - matching has to come from content, same as normalize.py); 5 more
Partner A records and 5 more Partner B records are deliberately given no
counterpart in the other partner's subset, exactly like the light-tower case
in the equipment-status demo, to test that Claude doesn't force bad matches.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python benchmark.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from recordlinkage.datasets import load_febrl4

from llm_client import AnthropicClient

ROOT = Path(__file__).parent
CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.MULTILINE)
N_MATCHED = 30
N_DISTRACTORS_EACH_SIDE = 5
RANDOM_SEED = 42


def extract_json(text: str) -> dict:
    try:
        return json.loads(CODE_FENCE_RE.sub("", text.strip()).strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Claude's response wasn't valid JSON: {exc}\nRaw response:\n{text}") from exc


def clean(val) -> str:
    return "" if pd.isna(val) else str(val)


def to_partner_a(new_id: str, row: pd.Series) -> dict:
    dob = clean(row["date_of_birth"])
    dob_fmt = f"{dob[4:6]}/{dob[6:8]}/{dob[0:4]}" if len(dob) == 8 else ""
    return {
        "person_id": new_id,
        "first_name": clean(row["given_name"]),
        "last_name": clean(row["surname"]),
        "street": f"{clean(row['street_number'])} {clean(row['address_1'])}".strip(),
        "city": clean(row["suburb"]),
        "postal_code": clean(row["postcode"]),
        "region": clean(row["state"]),
        "date_of_birth": dob_fmt,
        "id_number": clean(row["soc_sec_id"]),
    }


def to_partner_b(new_id: str, row: pd.Series) -> dict:
    dob = clean(row["date_of_birth"])
    dob_fmt = f"{dob[0:4]}.{dob[4:6]}.{dob[6:8]}" if len(dob) == 8 else ""
    return {
        "personId": new_id,
        "firstName": clean(row["given_name"]),
        "lastName": clean(row["surname"]),
        "streetAddress": f"{clean(row['address_1'])} {clean(row['street_number'])}".strip(),
        "cityName": clean(row["suburb"]),
        "postCode": clean(row["postcode"]),
        "regionCode": clean(row["state"]),
        "dateOfBirth": dob_fmt,
        "idNumber": clean(row["soc_sec_id"]),
    }


SYSTEM_PROMPT = """You are reconciling personnel roster records shared between
two coalition partners who each track the same people in their own system,
under different field-naming conventions, date formats, and record IDs with
no shared key. You are given Partner A's roster and Partner B's roster.

Match each Partner B record to its Partner A counterpart where one genuinely
exists, using name, date of birth, address, and ID-number similarity as
evidence (fields may have typos or formatting differences - don't require an
exact match, but don't force a pairing without real evidence). Some records
on either side may have no counterpart in the other roster - say so rather
than guessing.

Reply with ONLY JSON (no markdown fences):
{"matches": [{"partner_a_id": "...", "partner_b_id": "...", "confidence": "high|medium", "reasoning": "..."}],
 "unmatched_partner_a": ["..."], "unmatched_partner_b": ["..."]}
"""


def main() -> None:
    client = AnthropicClient()

    dfA, dfB, links = load_febrl4(return_links=True)
    all_pairs = list(links)

    sample_pairs = pd.Series(all_pairs).sample(n=N_MATCHED, random_state=RANDOM_SEED).tolist()
    matched_a_ids = [p[0] for p in sample_pairs]
    matched_b_ids = [p[1] for p in sample_pairs]

    remaining_a = dfA.index.difference(matched_a_ids)
    remaining_b = dfB.index.difference(matched_b_ids)
    distractor_a_ids = pd.Series(remaining_a).sample(n=N_DISTRACTORS_EACH_SIDE, random_state=RANDOM_SEED).tolist()
    distractor_b_ids = pd.Series(remaining_b).sample(n=N_DISTRACTORS_EACH_SIDE, random_state=RANDOM_SEED + 1).tolist()

    a_ids = matched_a_ids + distractor_a_ids
    b_ids = matched_b_ids + distractor_b_ids

    a_shuffled = pd.Series(a_ids).sample(frac=1, random_state=RANDOM_SEED + 2).tolist()
    b_shuffled = pd.Series(b_ids).sample(frac=1, random_state=RANDOM_SEED + 3).tolist()

    a_new_id = {orig: f"A-{i+1:03d}" for i, orig in enumerate(a_shuffled)}
    b_new_id = {orig: f"B-{i+1:03d}" for i, orig in enumerate(b_shuffled)}

    # hidden ground truth: new-id -> new-id for the true matches
    true_matches = {a_new_id[a]: b_new_id[b] for a, b in zip(matched_a_ids, matched_b_ids)}
    true_unmatched_a = {a_new_id[a] for a in distractor_a_ids}
    true_unmatched_b = {b_new_id[b] for b in distractor_b_ids}

    partner_a_records = [to_partner_a(a_new_id[orig], dfA.loc[orig]) for orig in a_shuffled]
    partner_b_records = [to_partner_b(b_new_id[orig], dfB.loc[orig]) for orig in b_shuffled]

    print(f"Partner A: {len(partner_a_records)} records ({N_MATCHED} matched + {N_DISTRACTORS_EACH_SIDE} distractors)")
    print(f"Partner B: {len(partner_b_records)} records ({N_MATCHED} matched + {N_DISTRACTORS_EACH_SIDE} distractors)\n")

    prompt = (
        f"Partner A roster:\n{json.dumps(partner_a_records, indent=2)}\n\n"
        f"Partner B roster:\n{json.dumps(partner_b_records, indent=2)}"
    )
    response = client.create(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}], max_tokens=6000)
    text = "".join(b.text for b in response.content if b.type == "text")
    result = extract_json(text)

    tp = fp = 0
    claimed_a = set()
    for m in result["matches"]:
        claimed_a.add(m["partner_a_id"])
        if true_matches.get(m["partner_a_id"]) == m["partner_b_id"]:
            tp += 1
        else:
            fp += 1
    fn = len(true_matches) - tp

    correctly_flagged_a = len(set(result["unmatched_partner_a"]) & true_unmatched_a)
    correctly_flagged_b = len(set(result["unmatched_partner_b"]) & true_unmatched_b)

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / len(true_matches)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else float("nan")

    report = [
        "# Febrl 4 Real-Data Benchmark Report (coalition-data-normalizer)",
        "",
        f"- True cross-partner matches: {len(true_matches)}",
        f"- Distractors (no true counterpart): {N_DISTRACTORS_EACH_SIDE} per side",
        f"- Claude true positives: {tp}, false positives: {fp}, false negatives: {fn}",
        f"- Precision: {precision:.2%}",
        f"- Recall: {recall:.2%}",
        f"- F1: {f1:.2%}",
        f"- Correctly flagged unmatched Partner A distractors: {correctly_flagged_a}/{N_DISTRACTORS_EACH_SIDE}",
        f"- Correctly flagged unmatched Partner B distractors: {correctly_flagged_b}/{N_DISTRACTORS_EACH_SIDE}",
    ]
    (ROOT / "benchmark_report.md").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print("\nWrote benchmark_report.md")


if __name__ == "__main__":
    main()
