# coalition-data-normalizer

Two synthetic partners track the same underlying equipment in incompatible
formats - different date conventions, units, field-naming styles, and status
vocabularies, with no shared primary key between their systems. Deterministic
code handles the mechanical conversion (units, dates); Claude handles the
genuinely ambiguous part: matching records across mismatched IDs, reconciling
status vocabularies that don't map 1:1, and flagging what it can't confidently
resolve instead of guessing.

`data/partner_a_records.json` and `data/partner_b_records.json` are entirely
synthetic sample data written for this demo - not from any real system, unit,
or data standard. This demonstrates a *class* of problem, not a real one.

## Why this exists

Two separate 2025/2026 US-ROK defense forums held at Camp Humphreys - the
C5ISRT Summit (Nov 2025) and KORDEF 2026 (Apr 2026) - both explicitly named
"data centrality for coalition data sharing and interoperability" as a
near-term priority. This is that problem, generic and safe: reconciling two
allies' incompatible equipment-status records into one canonical view.

## What makes the matching non-trivial

- One pair of records has a **transposed-digit typo** in the serial number
  (`GEN-330451-B` vs `GEN-330415-B`) - a clean string match fails, so the
  match has to come from corroborating evidence (asset type, usage hours,
  location, notes).
- One asset has a **status one partner tracks that the other doesn't** -
  Partner B's `MAINTENANCE-SCHEDULED` has no direct Partner A equivalent,
  forcing a real judgment call rather than a lookup table.
- One Partner B record (a light tower) has **no counterpart at all** in
  Partner A's data - the correct answer is to say so, not to force a match.

Live-run output for all three of these on the sample data is in
`output/interoperability_report.md` after running `normalize.py`.

## Architecture

```
data/partner_a_records.json  (US-style: MM/DD/YYYY, gallons, snake_case)
data/partner_b_records.json  (Partner-B style: YYYY.MM.DD, liters, camelCase)
        |
        v
  deterministic canonicalization (unit/date conversion only - no judgment calls)
        |
        v
  Claude reconciles: matches records, maps status vocabularies,
  flags unresolvable cases
        |
        v
  output/unified_assets.json
  output/interoperability_report.md
```

- `llm_client.py` - thin provider adapter. Anthropic is the tested backend
  used throughout this repo. OpenAI and Ask Sage adapters are included for
  the same interface, but have **not** been run against live credentials in
  this repo - treat them as reference code until verified.
- `normalize.py` - canonicalization + the reconciliation call described above.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your own ANTHROPIC_API_KEY
export $(grep -v '^#' .env | xargs)
python normalize.py
```

## Real-data benchmark

`normalize.py` above is an illustrative demo over ~13 hand-written equipment
records - useful for showing the architecture, but small enough that a
strong result isn't yet a measurement. `benchmark.py` is a separate,
additive scenario that measures the same reconciliation approach against
the **Febrl 4 record-linkage benchmark** (Christen, ANU), loaded via the
[`recordlinkage`](https://recordlinkage.readthedocs.io/) Python package.
Febrl 4 is a structural fit for this repo specifically: it's already split
into two 5,000-record tables with known 1:1 ground truth - i.e. already
shaped like "two partners, no shared key" before any reformatting.

Febrl is person-identity data (name/address/date-of-birth), not equipment
records - this isn't a replacement for the demo above, it's proof the
reconciliation *architecture* generalizes to a second, real domain
(personnel/roster reconciliation - a genuine coalition-interoperability need
in its own right), reformatted into the same Partner A / Partner B
field-naming and date-convention split as the equipment scenario, with 5
deliberately-unmatched decoy records per side (same test as the light-tower
case above - can it correctly say "no match" instead of forcing one).

**Actual measured result** (30 true matches + 5 distractors per side,
seed=42, full run in `benchmark_report.md`):

| Metric | Result |
|---|---|
| Precision | 100.00% (0 false positives) |
| Recall | 100.00% (0 false negatives) |
| Unmatched distractors correctly flagged | 10/10 |

```bash
python benchmark.py
```

## Deployment path

This demo calls the Anthropic API directly. A production version for a
coalition-facing DoD-adjacent client would more likely run through
**[Ask Sage](https://www.asksage.ai/)** - the IL5/IL6-authorized multi-model
gateway built for Defense Industrial Base contractors (`llm_client.py`
includes an `AskSageClient` built from Ask Sage's
[public API docs](https://github.com/Ask-Sage/AskSage-Open-Source-Community),
untested pending an account).

## Tests + CI

`test_normalize.py` and `test_benchmark.py` cover every deterministic
function (date-format parsing for both partner conventions, the
liters-to-gallons conversion math, the Partner A/B field reformatting,
JSON-fence stripping) - no API key or network needed, safe for CI on
every push:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Security notes

- API keys are read from environment variables only, never hardcoded;
  `.env` is gitignored, `.env.example` ships placeholders only.
- Checked (2026-07-18): this repository's full git history contains zero
  occurrences of any real API key.
- Network calls to the Ask Sage gateway have explicit 30s timeouts.
- A malformed/non-JSON model response now raises a clear, actionable
  error (with the raw response attached) instead of an opaque traceback.
- Dependencies are version-pinned with an upper bound
  (`>=X,<NEXT_MAJOR`), not left open-ended.

Built with [Claude Code](https://claude.com/claude-code).
