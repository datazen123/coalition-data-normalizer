"""
Coalition data interoperability demo: two synthetic partners track the same
underlying equipment in incompatible formats (dates, units, field names,
status vocabulary, and non-matching ID schemes). Deterministic code handles
the mechanical part (unit/date conversion); Claude handles the genuinely
ambiguous part - matching records across mismatched IDs, reconciling status
vocabularies that aren't a clean 1:1 mapping, and flagging anything it
can't confidently resolve rather than guessing.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python normalize.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from llm_client import AnthropicClient

ROOT = Path(__file__).parent
CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.MULTILINE)
LITERS_PER_GALLON = 3.78541


def extract_json(text: str) -> dict:
    return json.loads(CODE_FENCE_RE.sub("", text.strip()).strip())


def canon_a(rec: dict) -> dict:
    date_iso = datetime.strptime(rec["last_service_date"], "%m/%d/%Y").date().isoformat()
    return {
        "source": "A",
        "source_id": rec["vehicle_id"],
        "asset_type_raw": rec["asset_type"],
        "serial_raw": rec["serial_number"],
        "service_date_iso": date_iso,
        "usage_hours": rec["usage_hours"],
        "fuel_capacity_gal": rec["fuel_capacity_gal"],
        "status_raw": rec["status"],
        "location": rec["location_note"],
        "notes": rec["notes"],
    }


def canon_b(rec: dict) -> dict:
    date_iso = datetime.strptime(rec["lastServiceDate"], "%Y.%m.%d").date().isoformat()
    return {
        "source": "B",
        "source_id": rec["vehicleId"],
        "asset_type_raw": rec["assetType"],
        "serial_raw": rec["serialNo"],
        "service_date_iso": date_iso,
        "usage_hours": rec["usageHours"],
        "fuel_capacity_gal": round(rec["fuelCapacityL"] / LITERS_PER_GALLON, 1),
        "status_raw": rec["status"],
        "location": rec["locationNote"],
        "notes": rec["notes"],
    }


SYSTEM_PROMPT = """You are reconciling equipment-status records shared between
two coalition partners who each track the same physical assets in their own
system, with no shared primary key. You are given canonicalized (units/dates
already converted) records from Partner A and Partner B.

Your job - the part deterministic code can't do:
1. Match each Partner B record to its Partner A counterpart where one exists,
   using serial number similarity, asset type, usage hours, location, and
   notes as corroborating evidence (serials may have typos/transpositions -
   don't require an exact string match, but don't force a match without real
   evidence either).
2. Where Partner A and Partner B status vocabularies don't map 1:1 (e.g. a
   status one partner has that the other doesn't distinguish), propose a
   canonical status and explain the judgment call.
3. Explicitly list any Partner A or Partner B record you could not confidently
   match to the other side, with a one-line reason - do not force a match.

Reply with ONLY JSON (no markdown fences):
{"matches": [{"partner_a_id": "...", "partner_b_id": "...", "confidence": "high|medium",
  "match_reasoning": "...", "canonical_status": "...", "status_mapping_note": "..."}],
 "unmatched_partner_a": [{"id": "...", "reason": "..."}],
 "unmatched_partner_b": [{"id": "...", "reason": "..."}]}
"""


def reconcile(client: AnthropicClient, canon_a_list: list[dict], canon_b_list: list[dict]) -> dict:
    prompt = (
        f"Partner A records:\n{json.dumps(canon_a_list, indent=2)}\n\n"
        f"Partner B records:\n{json.dumps(canon_b_list, indent=2)}"
    )
    response = client.create(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in response.content if b.type == "text")
    return extract_json(text)


def main() -> None:
    client = AnthropicClient()

    a_records = json.loads((ROOT / "data" / "partner_a_records.json").read_text())
    b_records = json.loads((ROOT / "data" / "partner_b_records.json").read_text())

    canon_a_list = [canon_a(r) for r in a_records]
    canon_b_list = [canon_b(r) for r in b_records]

    print(f"Reconciling {len(canon_a_list)} Partner A records against {len(canon_b_list)} Partner B records...\n")
    result = reconcile(client, canon_a_list, canon_b_list)

    by_id_a = {r["source_id"]: r for r in canon_a_list}
    by_id_b = {r["source_id"]: r for r in canon_b_list}

    unified = []
    for m in result["matches"]:
        a = by_id_a.get(m["partner_a_id"])
        b = by_id_b.get(m["partner_b_id"])
        unified.append({
            "asset_type": a["asset_type_raw"] if a else (b["asset_type_raw"] if b else "unknown"),
            "partner_a_id": m["partner_a_id"],
            "partner_b_id": m["partner_b_id"],
            "canonical_status": m["canonical_status"],
            "usage_hours_a": a["usage_hours"] if a else None,
            "usage_hours_b": b["usage_hours"] if b else None,
        })

    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "unified_assets.json").write_text(json.dumps(unified, indent=2) + "\n")

    report_lines = [
        "# Interoperability Report",
        "",
        f"- Partner A records: {len(canon_a_list)}",
        f"- Partner B records: {len(canon_b_list)}",
        f"- Matched pairs: {len(result['matches'])}",
        f"- Unmatched Partner A: {len(result['unmatched_partner_a'])}",
        f"- Unmatched Partner B: {len(result['unmatched_partner_b'])}",
        "",
        "## Match decisions",
    ]
    for m in result["matches"]:
        report_lines.append(
            f"- **{m['partner_a_id']} <-> {m['partner_b_id']}** (confidence: {m['confidence']}): {m['match_reasoning']}"
        )
        if m.get("status_mapping_note"):
            report_lines.append(f"  - Status mapping: {m['status_mapping_note']}")
    report_lines.append("\n## Unmatched")
    for u in result["unmatched_partner_a"]:
        report_lines.append(f"- Partner A {u['id']}: {u['reason']}")
    for u in result["unmatched_partner_b"]:
        report_lines.append(f"- Partner B {u['id']}: {u['reason']}")

    (ROOT / "output" / "interoperability_report.md").write_text("\n".join(report_lines) + "\n")
    print("\n".join(report_lines))
    print(f"\nWrote output/unified_assets.json and output/interoperability_report.md")


if __name__ == "__main__":
    main()
