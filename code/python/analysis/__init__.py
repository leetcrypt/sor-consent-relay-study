"""R7 (partial) — offline analysis calibration primitives.

This package holds only the *offline-validatable* half of R7: the detectors that
the instrument-validation gate calibrates on **synthetic fixtures** (never on
confirmatory-cell data — CLAUDE.md build discipline). Specifically:

- ``detectors.shannon_entropy_bits`` — the RQ2 anonymity-set entropy metric; gate
  item 4 requires it to return ``log2(N)`` for ``N`` equiprobable senders.
- ``detectors.bridge_correlation_auc`` — the RQ1 bridge-linkability scorer; gate
  item 3 requires AUC ≈ 1 on a known-linked control pair and ≈ 0.5 on a
  known-unlinked pair.

These are pure functions over in-memory series/distributions — they read no
pcaps, spawn no engine, move no traffic, and touch no VM fabric.

The rest of R7 is landed alongside: ``metrics.py`` (this package) aggregates the
four DV families into a schema-valid, write-once ``metrics.json``; the seeded
churn schedule + rebuild loop live in ``cmd_chat/sor/{churn,selector}.py``. The
live VM spin/kill against the isolated hackhouse fabric, and the full
pre-registered confirmatory battery, remain gated by the containment law + the
human freeze (see OVERSEER-STATUS.md) — the churn schedule is seeded *data* here,
not a real VM operation.
"""
