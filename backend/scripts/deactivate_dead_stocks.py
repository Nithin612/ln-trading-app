"""⛔ RETIRED 2026-09-14 (D2′b). This script no longer runs.

**What it did.** It deactivated stocks absent from `kite_instruments` — the only
`UPDATE stocks SET is_active` statement in the repository.

**Where the logic went.** Into the universe rule's `KITE_TRADABLE` term
(`app/services/universe_rule.py`). The rule now evaluates nightly and records its
verdict in `universe_snapshot`; `universe_materialiser.apply_to_stocks` is the single
writer, and a database trigger refuses every other one. So this script's job is done
continuously and reversibly instead of imperatively and once.

    uv run python scripts/universe_snapshot.py --diff     # what would change
    uv run python scripts/universe_snapshot.py --apply    # materialise and adopt

⛔ **Its documented reversal SQL has been REMOVED, not preserved, and that is the
point.** It joined on raw `stock_id`, and every id in this database was reassigned
during the 2026-09-07 rebuild — plan §20/2 measured the consequence: July's
`stock_id = 228` was `QUINTEGRA` and today's is `BSE`, so running that reversal would
have reactivated *the wrong companies*. Keeping a loaded reversal in a docstring where
someone might paste it was the hazard. To undo a universe change now, re-materialise
for the date you want and apply that.

⚠ Its forensic table `forensic_stocks_deactivated` did not survive the 2026-09-07
database loss, so the 15 July deactivation judgements are gone and could not be used
as an acceptance test for the rule. `universe_snapshot` is the durable replacement:
dated, per-stock, and reproducible.
"""

import sys

_MESSAGE = __doc__ or ""


def main() -> int:
    print(_MESSAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
