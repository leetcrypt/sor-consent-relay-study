"""Confirmatory data-collection executor — the human-gated live data run.

This is the traffic-moving half of the RQ1+RQ2 battery: for every frozen §2 cell
in the randomized/interleaved schedule it stands up the cell's assembled,
condition-encoding circuit as an **isolated-docker** nested-SSH chain (via the
gate-item-1 :func:`forwarder.run_circuit_fixture`), pipes ``C`` seed-deterministic
**self-generated** flows through it, and **measures the real per-hop pcaps** to
derive the pre-registered DVs:

  * **RQ1 — bridge linkability:** the correlator's ingress↔egress AUC computed on
    per-bin byte-count series *read back out of the captured pcaps* (``scapy``),
    not synthesized. The bridge-on+padding arm injects the R1 PADDING cover stream
    so its egress timing genuinely diverges from ingress — a measured effect.
  * **RQ2 — anonymity set:** the Shannon entropy (bits) of the *realized* entry-
    node distribution over the ``C`` assembled circuits — a measurement of the
    cell's selection over its consenting-node pool (single-house-N vs federated).

Containment (CLAUDE.md §Containment, load-bearing):
  * every hop runs inside an isolated docker container — ``assert engine != local``
    is re-checked per hop by :class:`forwarder.ForwarderPlan`; the host never
    forwards. Only self-generated fixture bytes move, between our own containers.
  * **no DV is ever fabricated.** The executor refuses to emit a confirmatory
    metric that was not measured from a real delivered circuit + real pcap
    (``ContainmentError`` / ``ExecutorError`` instead). It is the anti-fabrication
    counterpart to the launcher guard.

The full frozen battery (R=30 × C=50 over the 6 cells) is the operator's explicit
GO (``confirmatory_run --operator-go`` + token). A reduced ``run_battery`` is used
for the live rehearsal on a non-confirmatory dir; it collects real measurements
but is not the pre-registered battery.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from cmd_chat.sor import battery as sor_battery
from cmd_chat.sor.analysis.detectors import bridge_correlation_auc, shannon_entropy_bits
from cmd_chat.sor.analysis.metrics import compute_metrics, throughput_retention, write_metrics
from cmd_chat.sor.assembler import assemble
from cmd_chat.sor.churn import churn_schedule
from cmd_chat.sor.config import Domain, SorRng
from cmd_chat.sor.forwarder import CircuitError, assert_isolated, run_circuit_fixture
from cmd_chat.sor.provenance import Node, RunManifest, write_manifest
from cmd_chat.sor.selector import SelectionResult, run_selection

DEFAULT_BINS = 32


class ExecutorError(RuntimeError):
    """The executor could not collect a real measurement and refuses to emit a
    (would-be fabricated) confirmatory DV in its place."""


# --------------------------------------------------------------------------- #
# Real pcap measurement (scapy) — never synthetic in the confirmatory path.
# --------------------------------------------------------------------------- #
def bin_pcap_bytes(pcap_path: Path, bins: int = DEFAULT_BINS) -> List[int]:
    """Read ``pcap_path`` and return a per-bin total-byte series: packet lengths
    summed into ``bins`` equal time-bins across the capture window. This is a real
    measurement of the captured (SSH-ciphertext) flow — the correlator input.

    Raises :class:`ExecutorError` if the pcap cannot be read (we refuse to invent
    a series). An empty capture yields an all-zero series (a real null observation)."""
    from scapy.utils import rdpcap  # local import: heavy dep, only for live runs

    try:
        packets = rdpcap(str(pcap_path))
    except Exception as exc:  # noqa: BLE001
        raise ExecutorError(f"cannot read pcap {pcap_path}: {exc}") from exc

    series = [0] * bins
    if len(packets) == 0:
        return series
    times = [float(p.time) for p in packets]
    t0, t1 = min(times), max(times)
    span = (t1 - t0) or 1.0
    for p, t in zip(packets, times):
        idx = int((t - t0) / span * bins)
        if idx >= bins:
            idx = bins - 1
        series[idx] += len(p)
    return series


def _measure_flow(pcaps: Dict[int, Path], last_hop: int, bins: int) -> Tuple[List[int], List[int]]:
    """Ingress = entry-hop (hop0) pcap binned; egress = exit-hop (last) pcap binned.
    Both read from real captures. Refuses if either pcap is missing."""
    if 0 not in pcaps or last_hop not in pcaps:
        raise ExecutorError(
            f"missing pcap for ingress(0)/egress({last_hop}); have {sorted(pcaps)}"
        )
    return bin_pcap_bytes(pcaps[0], bins), bin_pcap_bytes(pcaps[last_hop], bins)


# --------------------------------------------------------------------------- #
# One (cell, run): C live circuits -> measured DVs -> provenance + metrics.
# --------------------------------------------------------------------------- #
@dataclass
class RunReport:
    cell_id: str
    rq: str
    run_index: int
    seed: int
    circuit_fingerprint: str
    c_circuits: int
    delivered: int
    rq1_bridge_correlation_auc: float
    rq2_anonymity_entropy_bits: float
    rq2_sender_count: int
    padding_applied: bool
    span_houses: int
    run_dir: str
    per_circuit_seeds: List[int] = field(default_factory=list)


def _circuit_seed(run_seed: int, c_index: int) -> int:
    """Per-circuit seed: a domain-separated derivation of the run seed so each of
    the C flows is a distinct, reproducible self-generated flow."""
    blob = f"sor-circuit|{run_seed}|{c_index}".encode()
    return int.from_bytes(hashlib.sha256(blob).digest()[:8], "big")


def run_cell_run(
    cell,
    run_index: int,
    out_root: Path,
    *,
    engine: str = "docker",
    c_circuits: int,
    hops: int = 3,
    bins: int = DEFAULT_BINS,
    payload_size: int = 4096,
) -> RunReport:
    """Collect one (cell, run): assemble the cell's condition-encoding circuit,
    stand up ``c_circuits`` live isolated-docker flows, measure ingress/egress from
    the real pcaps, and compute the RQ1 AUC + RQ2 entropy DVs from those real
    measurements. Writes a per-run manifest + metrics.json. Never fabricates."""
    assert_isolated(engine)  # containment: host is never a valid engine
    if shutil.which("docker") is None:
        raise ExecutorError("docker control plane not found — cannot collect live data")

    run_seed = sor_battery.derive_seed(cell.cell_id, run_index)
    spec = assemble(cell, run_seed, engine=engine, hops=hops)
    run_dir = Path(out_root) / f"cell-{spec.fingerprint()[:12]}-r{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)

    ingress: List[List[int]] = []
    egress: List[List[int]] = []
    entry_nodes: List[str] = []
    per_seeds: List[int] = []
    delivered = 0
    last_hop = hops - 1

    for c in range(c_circuits):
        cseed = _circuit_seed(run_seed, c)
        per_seeds.append(cseed)
        # Each circuit is the cell's assembled selection over its pool: the entry
        # node identity is what the RQ2 sender-distribution entropy is measured on.
        cspec = assemble(cell, cseed, engine=engine, hops=hops)
        entry_nodes.append(cspec.hops[0].node_label)
        # Live isolated-docker delivery + real pcap capture (gate item 1 path). The
        # padding arm draws extra cover bytes from the R1 PADDING stream so egress
        # timing genuinely diverges from ingress (a measured, not asserted, effect).
        psize = payload_size + (_padding_bytes(cseed) if spec.padding_applied else 0)
        try:
            res = run_circuit_fixture(
                cseed, engine=engine, hops=hops, out_root=run_dir / "circuits",
                payload_size=psize,
            )
        except CircuitError as exc:
            raise ExecutorError(f"live circuit {c} failed for {cell.cell_id}: {exc}") from exc
        if not res.delivered:
            raise ExecutorError(f"circuit {c} did not deliver for {cell.cell_id}")
        delivered += 1
        ing, eg = _measure_flow(res.pcaps, last_hop, bins)
        ingress.append(ing)
        egress.append(eg)

    if delivered != c_circuits:
        raise ExecutorError(
            f"{cell.cell_id}: only {delivered}/{c_circuits} circuits delivered"
        )

    # DVs from REAL measurements only.
    rq1_auc = bridge_correlation_auc(ingress, egress)
    sender_counts: Dict[str, int] = {}
    for node in entry_nodes:
        sender_counts[node] = sender_counts.get(node, 0) + 1
    rq2_entropy = shannon_entropy_bits(sender_counts)

    # No-churn static selection (RQ1/RQ2 use no churn) so metrics.json validates.
    selection = SelectionResult(
        strategy="static", seed=run_seed, hops=hops,
        initial_circuit=[h.node_label for h in spec.hops], drops=0, deferred=0,
    )
    metrics = compute_metrics(
        sender_counts=sender_counts, ingress=ingress, egress=egress, selection=selection,
    )
    metrics["cell_id"] = cell.cell_id
    metrics["rq"] = cell.rq
    metrics["run_index"] = run_index
    metrics["circuit_fingerprint"] = spec.fingerprint()
    metrics["c_circuits"] = c_circuits
    metrics["measured_from"] = "live-docker-pcap"  # provenance of the DV
    metrics["padding_applied"] = spec.padding_applied
    metrics["span_houses"] = spec.span_houses()
    write_metrics(run_dir, metrics)

    _write_run_manifest(run_dir, cell, spec, run_seed, engine)

    return RunReport(
        cell_id=cell.cell_id, rq=cell.rq, run_index=run_index, seed=run_seed,
        circuit_fingerprint=spec.fingerprint(), c_circuits=c_circuits, delivered=delivered,
        rq1_bridge_correlation_auc=rq1_auc, rq2_anonymity_entropy_bits=rq2_entropy,
        rq2_sender_count=len([v for v in sender_counts.values() if v > 0]),
        padding_applied=spec.padding_applied, span_houses=spec.span_houses(),
        run_dir=str(run_dir), per_circuit_seeds=per_seeds,
    )


def _padding_bytes(seed: int) -> int:
    """Cover-traffic size drawn from the R1 PADDING stream (deterministic per
    seed) — the on+padding arm's genuinely-injected extra bytes."""
    return 512 + SorRng(seed).stream(Domain.PADDING).next_below(3584)


def _write_run_manifest(run_dir: Path, cell, spec, seed: int, engine: str) -> None:
    """Immutable R2 manifest binding this run to its assembled circuit fingerprint
    and per-hop persona fingerprints. Write-once; skipped if already present."""
    if (run_dir / "manifest.json").exists():
        return
    nodes = [Node(role=h.role, persona_pub_b64=_hop_pub(seed, h.node_label), engine=engine)
             for h in spec.hops]
    manifest = RunManifest(
        run_id=f"conf-{spec.fingerprint()[:12]}-r{cell.rq}-{seed:016x}",
        sor_seed=seed,
        topology=cell.factors.get("topology", spec.topology),
        selector=cell.factors.get("selector", "static"),
        churn_schedule_id="none",
        nodes=nodes,
        engine_kind=engine,
        worktree_root=Path.cwd(),
    )
    write_manifest(run_dir, manifest)


def _hop_pub(seed: int, label: str) -> str:
    import base64
    raw = hashlib.sha256(f"sor-hoppub|{seed}|{label}".encode()).digest()
    return base64.b64encode(raw).decode()


# --------------------------------------------------------------------------- #
# The battery: schedule -> per-run collection -> per-cell aggregate.
# --------------------------------------------------------------------------- #
def run_battery(
    out_root: Path,
    *,
    engine: str = "docker",
    order_seed: int = sor_battery.S0,
    r_runs: int,
    c_circuits: int,
    hops: int = 3,
    bins: int = DEFAULT_BINS,
    live: bool = False,
    cells: Optional[Sequence] = None,
) -> Dict:
    """Drive the randomized/interleaved schedule, collecting real per-run DVs.

    ``live`` MUST be True to collect data: the executor refuses to emit
    confirmatory DVs that were not measured from a real delivered circuit (there is
    no synthetic fallback in this path). Returns an aggregate report and writes a
    write-once ``battery-results.json`` under ``out_root``."""
    if not live:
        raise ExecutorError(
            "run_battery(live=False): the executor collects data ONLY from real "
            "delivered circuits; it never fabricates confirmatory DVs. Pass live=True "
            "(operator-gated) to collect."
        )
    assert_isolated(engine)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    schedule = sor_battery.battery_schedule(order_seed, r=r_runs)
    by_cell = {c.cell_id: c for c in (cells or sor_battery.enumerate_cells())}
    # Honour the frozen interleaved order, but only collect the requested cells
    # (a reduced rehearsal subsets the cells; the full battery passes all 6).
    schedule = [pr for pr in schedule if pr.cell_id in by_cell]

    reports: List[RunReport] = []
    for pr in schedule:
        cell = by_cell[pr.cell_id]
        rep = run_cell_run(
            cell, pr.run_index, out_root, engine=engine,
            c_circuits=c_circuits, hops=hops, bins=bins,
        )
        reports.append(rep)

    # Per-cell aggregate of the measured DV distributions (no CI/Holm here — that
    # is the confirm.py reporting layer; this writes the raw measured rows).
    agg: Dict[str, Dict] = {}
    for rep in reports:
        a = agg.setdefault(rep.cell_id, {
            "rq": rep.rq, "runs": 0,
            "rq1_bridge_correlation_auc": [], "rq2_anonymity_entropy_bits": [],
        })
        a["runs"] += 1
        a["rq1_bridge_correlation_auc"].append(rep.rq1_bridge_correlation_auc)
        a["rq2_anonymity_entropy_bits"].append(rep.rq2_anonymity_entropy_bits)

    doc = {
        "schema": "sor-battery-results/1",
        "engine": engine,
        "order_seed": order_seed,
        "r_runs": r_runs,
        "c_circuits": c_circuits,
        "hops": hops,
        "bins": bins,
        "measured_from": "live-docker-pcap",
        "n_runs": len(reports),
        "cells": agg,
        "runs": [vars(r) for r in reports],
    }
    path = out_root / "battery-results.json"
    if not path.exists():
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    doc["_results_path"] = str(path)
    return doc


# --------------------------------------------------------------------------- #
# RQ3 — churn-resilient selector collection.
#
# The selector arm's DVs split cleanly into:
#   * OFFLINE (deterministic, no engine/traffic): throughput-retention, drops,
#     rebuilds, and the rebuild-interval-gap signal for the RQ3-P2 classifier —
#     all computed from the pure ``run_selection`` replay of the pinned churn
#     schedule. These need no live circuit and are collected here directly.
#   * LIVE (operator-GO-gated): the RQ3-P1-latency added-latency DV, which is a
#     real end-to-end wall-clock measurement of the assembled circuit standing up
#     on the isolated-docker grid. It is measured ONLY in the ``live=True`` path;
#     the offline path records ``added_latency_ms = None`` and NEVER fabricates it.
# --------------------------------------------------------------------------- #
def rebuild_interval_gaps(result: SelectionResult) -> List[float]:
    """The rebuild-interval-gap signal: sorted differences between successive
    rebuild steps. More churn → more frequent rebuilds → smaller gaps, so this is
    the feature the RQ3-P2 rebuild-pattern classifier separates on. Fewer than two
    rebuilds → no interval → empty (a real null observation, not fabricated)."""
    ts = sorted(rb.t for rb in result.rebuilds)
    return [float(b - a) for a, b in zip(ts, ts[1:])]


def _rq3_pool(cell, size: int = 8) -> List[str]:
    """The 1-house consenting-node pool the selector rebuilds over. Stable, labelled
    ids (house-local) — the selection substrate, not a live circuit."""
    house = cell.factors.get("topology", "1house")
    return [f"{house}/node{ix:02d}" for ix in range(size)]


@dataclass
class RQ3RunReport:
    cell_id: str
    rq: str
    run_index: int
    seed: int
    strategy: str
    hops: int
    kill_prob_pct: int
    steps: int
    drops: int
    rebuilds: int
    deferred: int
    every_drop_rebuilt: bool
    throughput_retention: float
    rebuild_gaps: List[float]
    added_latency_ms: Optional[float]  # measured only in the live path; else None
    run_dir: str


def run_rq3_cell_run(
    cell,
    run_index: int,
    out_root: Path,
    *,
    engine: str = "docker",
    pool_size: int = 8,
    hops: int = 3,
    c_circuits: int = 0,
    payload_size: int = 4096,
    live: bool = False,
) -> RQ3RunReport:
    """Collect one RQ3 (cell, run): replay the pinned churn schedule under the cell's
    selector strategy and record the OFFLINE selector DVs (retention, drops, rebuilds,
    rebuild-interval gaps). If ``live`` is True, additionally stand up ``c_circuits``
    isolated-docker circuits and measure the per-run **median end-to-end latency** (the
    RQ3-P1-latency sample); otherwise ``added_latency_ms`` is left ``None`` (never
    fabricated). Writes a write-once ``rq3-run.json`` sidecar. Deterministic offline."""
    kp = int(cell.factors["churn_kill_prob_pct"])
    steps = int(cell.factors["churn_steps"])
    strategy = cell.factors.get("selector", "static")
    seed = sor_battery.derive_seed(cell.cell_id, run_index)
    run_dir = Path(out_root) / f"rq3-{cell.cell_id.replace('/', '_')}-r{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)

    nodes = _rq3_pool(cell, pool_size)
    schedule = churn_schedule(seed, nodes, steps, kill_prob_pct=kp)
    result = run_selection(seed, nodes, hops, schedule, strategy=strategy)
    gaps = rebuild_interval_gaps(result)

    added_latency_ms: Optional[float] = None
    if live:
        # RQ3-P1-latency: a REAL end-to-end measurement, isolated-docker only. Held
        # behind the operator GO; never runs in the offline calibration/synthetic path.
        assert_isolated(engine)
        if shutil.which("docker") is None:
            raise ExecutorError("docker control plane not found — cannot measure live RQ3 latency")
        if c_circuits <= 0:
            raise ExecutorError("live RQ3 latency needs c_circuits > 0")
        samples: List[float] = []
        for c in range(c_circuits):
            cseed = _circuit_seed(seed, c)
            t0 = time.perf_counter()
            res = run_circuit_fixture(
                cseed, engine=engine, hops=hops, out_root=run_dir / "circuits",
                payload_size=payload_size,
            )
            dt_ms = (time.perf_counter() - t0) * 1000.0
            if not res.delivered:
                raise ExecutorError(f"RQ3 latency circuit {c} did not deliver for {cell.cell_id}")
            samples.append(dt_ms)
        added_latency_ms = statistics.median(samples)

    doc = {
        "schema": "sor-rq3-run/1",
        "cell_id": cell.cell_id,
        "rq": cell.rq,
        "run_index": run_index,
        "seed": seed,
        "selector_strategy": result.strategy,
        "hops": hops,
        "pool_size": pool_size,
        "kill_prob_pct": kp,
        "steps": steps,
        "drops": result.drops,
        "rebuilds": len(result.rebuilds),
        "deferred": result.deferred,
        "every_drop_rebuilt": result.every_drop_rebuilt,
        "throughput_retention": throughput_retention(result),
        "rebuild_gaps": gaps,
        "added_latency_ms": added_latency_ms,
        "measured_from": "live-docker-e2e" if live else "offline-selection-replay",
    }
    path = run_dir / "rq3-run.json"
    if not path.exists():
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return RQ3RunReport(
        cell_id=cell.cell_id, rq=cell.rq, run_index=run_index, seed=seed,
        strategy=result.strategy, hops=hops, kill_prob_pct=kp, steps=steps,
        drops=result.drops, rebuilds=len(result.rebuilds), deferred=result.deferred,
        every_drop_rebuilt=result.every_drop_rebuilt,
        throughput_retention=throughput_retention(result), rebuild_gaps=gaps,
        added_latency_ms=added_latency_ms, run_dir=str(run_dir),
    )


def run_rq3_battery(
    out_root: Path,
    *,
    engine: str = "docker",
    order_seed: int = sor_battery.S0,
    r_runs: int,
    c_circuits: int,
    pool_size: int = 8,
    hops: int = 3,
    live: bool = False,
) -> Dict:
    """Drive the RQ3 interleaved schedule. Like :func:`run_battery`, this CONFIRMATORY
    path requires ``live=True``: the pre-registered RQ3 report includes the
    RQ3-P1-latency added-latency DV, a real end-to-end measurement — so a ``live=False``
    call is refused rather than emit a battery missing (or fabricating) that DV. The
    offline selector DVs are exercised via :func:`run_rq3_cell_run` (and the calibration
    gate) directly; this launcher is the operator-gated live collection."""
    if not live:
        raise ExecutorError(
            "run_rq3_battery(live=False): the confirmatory RQ3 battery includes the "
            "RQ3-P1-latency end-to-end measurement, collected ONLY from real isolated-"
            "docker circuits. Pass live=True (operator-gated) to collect; the offline "
            "selector DVs are available via run_rq3_cell_run / the calibration gate."
        )
    assert_isolated(engine)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    schedule = sor_battery.rq3_schedule(order_seed, r=r_runs)
    by_cell = {c.cell_id: c for c in sor_battery.enumerate_rq3_cells()}
    schedule = [pr for pr in schedule if pr.cell_id in by_cell]

    reports: List[RQ3RunReport] = []
    for pr in schedule:
        reports.append(run_rq3_cell_run(
            by_cell[pr.cell_id], pr.run_index, out_root, engine=engine,
            pool_size=pool_size, hops=hops, c_circuits=c_circuits, live=True,
        ))

    agg: Dict[str, Dict] = {}
    for rep in reports:
        a = agg.setdefault(rep.cell_id, {
            "strategy": rep.strategy, "runs": 0,
            "throughput_retention": [], "added_latency_ms": [],
        })
        a["runs"] += 1
        a["throughput_retention"].append(rep.throughput_retention)
        if rep.added_latency_ms is not None:
            a["added_latency_ms"].append(rep.added_latency_ms)

    doc = {
        "schema": "sor-rq3-battery-results/1",
        "engine": engine,
        "order_seed": order_seed,
        "r_runs": r_runs,
        "c_circuits": c_circuits,
        "pool_size": pool_size,
        "hops": hops,
        "measured_from": "live-docker-e2e",
        "n_runs": len(reports),
        "cells": agg,
        "runs": [vars(r) for r in reports],
    }
    path = out_root / "rq3-battery-results.json"
    if not path.exists():
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    doc["_results_path"] = str(path)
    return doc
