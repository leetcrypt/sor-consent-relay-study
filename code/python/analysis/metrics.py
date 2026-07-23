"""R7 — metrics.json aggregator (the DV writer for a SOR run).

Reads the offline detector primitives (``detectors.py``) plus a churn/selector
:class:`~cmd_chat.sor.selector.SelectionResult` and writes an immutable, schema-
valid ``metrics.json`` into a run directory. It aggregates the four DV families
the study reports:

  * RQ1 — bridge-correlation AUC (linkability of ingress↔egress flows);
  * RQ2 — anonymity-set entropy (bits) of the observed sender distribution;
  * RQ3 — throughput retention under churn + a rebuild-pattern classifier AUC.

The detectors are calibrated on synthetic fixtures only (never fit to
confirmatory-cell data — CLAUDE.md build discipline). This module computes and
serializes; it moves no traffic and spawns no engine. ``metrics.json`` is written
once and never edited in place (artifact immutability)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from cmd_chat.sor.analysis.detectors import (
    auc,
    bridge_correlation_auc,
    shannon_entropy_bits,
)
from cmd_chat.sor.selector import SelectionResult

METRICS_SCHEMA = "sor-metrics/1"


def throughput_retention(result: SelectionResult) -> float:
    """Fraction of dropped circuits that were successfully rebuilt (a proxy for
    throughput retained under churn). 1.0 when every drop was healed; lower when
    drops were deferred for lack of a live pool. No drops -> full retention."""
    if result.drops <= 0:
        return 1.0
    healed = result.drops - result.deferred
    return max(0.0, min(1.0, healed / result.drops))


def rebuild_classifier_auc(
    churned_gaps: Sequence[float], baseline_gaps: Sequence[float]
) -> float:
    """AUC separating a churned run's rebuild-interval signal from a low-churn
    baseline's — the RQ3 rebuild-pattern classifier. ≈1 when the two regimes are
    cleanly separable, ≈0.5 when indistinguishable. Calibrated on labeled control
    signals, not fit to confirmatory data."""
    # Shorter gaps (more frequent rebuilds) mark the churned regime; score churned
    # as the positive class on the negated gap so larger score = more churn.
    pos = [-g for g in churned_gaps]
    neg = [-g for g in baseline_gaps]
    return auc(pos, neg)


def compute_metrics(
    *,
    sender_counts: Dict[str, int],
    ingress: Sequence[Sequence[float]],
    egress: Sequence[Sequence[float]],
    selection: SelectionResult,
    churned_gaps: Optional[Sequence[float]] = None,
    baseline_gaps: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Aggregate the four DV families into a metrics dict (not yet written)."""
    metrics: Dict[str, Any] = {
        "schema": METRICS_SCHEMA,
        "seed": selection.seed,
        "selector_strategy": selection.strategy,
        "hops": selection.hops,
        "rq1_bridge_correlation_auc": bridge_correlation_auc(ingress, egress),
        "rq2_anonymity_entropy_bits": shannon_entropy_bits(sender_counts),
        "rq2_sender_count": len([c for c in sender_counts.values() if c > 0]),
        "rq3_throughput_retention": throughput_retention(selection),
        "rq3_drops": selection.drops,
        "rq3_rebuilds": len(selection.rebuilds),
        "rq3_deferred": selection.deferred,
        "rq3_every_drop_rebuilt": selection.every_drop_rebuilt,
    }
    if churned_gaps is not None and baseline_gaps is not None:
        metrics["rq3_rebuild_classifier_auc"] = rebuild_classifier_auc(
            churned_gaps, baseline_gaps
        )
    return metrics


def _validate(metrics: Dict[str, Any]) -> None:
    required = (
        "schema",
        "rq1_bridge_correlation_auc",
        "rq2_anonymity_entropy_bits",
        "rq3_throughput_retention",
        "rq3_every_drop_rebuilt",
    )
    missing = [k for k in required if k not in metrics]
    if missing:
        raise ValueError(f"metrics schema: missing keys {missing}")
    if metrics["schema"] != METRICS_SCHEMA:
        raise ValueError(f"metrics schema: unexpected {metrics['schema']!r}")


def write_metrics(run_dir: Path, metrics: Dict[str, Any]) -> Path:
    """Write ``metrics.json`` into ``run_dir`` (created if needed) and return its
    path. Refuses to overwrite an existing metrics.json (write-once artifact)."""
    _validate(metrics)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "metrics.json"
    if path.exists():
        raise FileExistsError(f"metrics.json already exists (immutable): {path}")
    path.write_text(json.dumps(metrics, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path
