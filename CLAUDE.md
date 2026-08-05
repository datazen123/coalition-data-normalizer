# Context for Claude Code working in this repo

This repo is one of a **10-repo public portfolio** (github.com/datazen123)
demonstrating real, live-verified agentic AI engineering for a specific
DoD-contractor job pursuit. Full README below covers this repo in detail;
this file covers conventions and status a coding agent needs before making
changes.

## This repo's role

Claude reconciles two synthetic allied partners' incompatible
equipment-status data formats (mismatched IDs, non-1:1 status vocabulary);
deterministic code handles unit/date conversion. **Weakest award evidence
in the portfolio** - no named ROK-US contract found, grounded instead in
the stated priority at the Nov 2025 C5ISRT Summit / Apr 2026 KORDEF plus a
theater-level (not peninsula-specific) Palantir Joint Fires Network award.

**Status**: 9/9 tests passing. Real benchmark against the Febrl 4
record-linkage benchmark: 100% precision, 100% recall, all 10 deliberate
no-match decoys correctly flagged.

**Not yet given the "deep pass"** (deterministic escalation gate /
verifier-with-correction-loop pattern) applied to the more recently-worked
repos - on the punch list, not done. Lower priority given the weaker
evidence base.

## Non-negotiable discipline this whole portfolio follows

1. Never fabricate a source - every real-data claim is independently
   fetched/verified.
2. Deterministic code owns any mechanical computation; Claude only
   handles the genuinely ambiguous/language part.
3. Live-verify against the real Anthropic API before claiming a result.
4. Synthetic demo data is always labeled as synthetic; real external data
   is cited with exact source.
5. Pytest suite, GitHub Actions CI, "Security notes" README section,
   pinned dependencies.
6. No real client, unit, or classified-sounding content ever.
7. Ask Sage (not Claude directly) is named as the realistic DoD/DIB
   production deployment path.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill in your own ANTHROPIC_API_KEY, never commit it
pytest -q
```

Full cross-repo strategy, founder research, and environment notes live in
this portfolio's private cross-repo context repo - not duplicated here
since this repo is public.
